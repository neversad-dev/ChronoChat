import os
import sys
import asyncio
import questionary
import config
import auth
import metadata
import signal_backup
import db
from menu import menu_select, ask_text, ask_confirm
from telethon import errors
from telethon.tl.types import InputMessagesFilterPhotoVideo, InputMessagesFilterDocument

async def prompt_credentials():
    print("\n[!] Please enter your Telegram API credentials.")
    print("[!] Get them from https://my.telegram.org/ \n")
    
    api_id_str = await ask_text("Enter your App api_id (integer):")
    if not api_id_str or not api_id_str.isdigit():
        print("[-] Invalid api_id. It must be an integer.")
        return

    api_hash = await ask_text("Enter your App api_hash (string):")
    if not api_hash:
        print("[-] api_hash cannot be empty.")
        return

    api_id = int(api_id_str)
    print("[+] Validating credentials (connecting to Telegram)...")
    is_valid, msg = await auth.validate_credentials(api_id, api_hash)
    
    if is_valid:
        config.save_credentials(api_id, api_hash)
        print("[+] Credentials saved successfully!\n")
    else:
        print(f"[-] Failed to validate credentials: {msg}\n")

async def handle_login(client):
    print("\n[+] Initiating login sequence...")
    phone = await ask_text("Enter your phone number (e.g. +1234567890):")
    if not phone: return
    
    try:
        await client.send_code_request(phone)
        code = await ask_text("Enter the code you received:")
        
        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            password = await ask_text("Two-step verification is enabled. Enter your password:", password=True)
            await client.sign_in(password=password)
            
        me = await client.get_me()
        print(f"[+] Logged in successfully as {me.first_name}!\n")
    except Exception as e:
        print(f"[-] Login failed: {e}\n")

async def _process_message(client, message, chat_id, save_dir, sem):
    status = await db.get_status(chat_id, message.id)
    if status == 'success':
        return 'skipped'

    async with sem:
        try:
            # Small delay to respect Telegram's rate limits when downloading in parallel
            await asyncio.sleep(0.3)
            path = await client.download_media(message, file=save_dir)
            if path:
                if message.date:
                    metadata.adjust_media_metadata(path, message.date)
                await db.update_status(chat_id, message.id, 'success')
                print(f"[+] Downloaded {os.path.basename(path)}")
                return 'success'
            else:
                await db.update_status(chat_id, message.id, 'failure', 'Empty path returned')
                return 'failure'
        except Exception as e:
            await db.update_status(chat_id, message.id, 'failure', str(e))
            print(f"[-] Failed message {message.id}: {e}")
            return 'failure'

async def download_chat_media(client, dialog):
    print(f"\n[*] Downloading media from '{dialog.title or 'Unknown'}'...")
    raw_title = dialog.title
    if not raw_title or not raw_title.strip():
        safe_title = f"chat_{dialog.id}"
    else:
        safe_title = "".join([c for c in raw_title if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
        if not safe_title:
            safe_title = f"chat_{dialog.id}"
    base_dir = config.get_download_dir()
    save_dir = os.path.join(base_dir, "telegram", safe_title)
    os.makedirs(save_dir, exist_ok=True)

    sem = asyncio.Semaphore(5)
    tasks = set()
    MAX_TASKS = 100

    async def _wait_tasks(min_len=0):
        while len(tasks) > min_len:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            tasks.difference_update(done)

    try:
        print("[*] Processing photos and videos...")
        async for message in client.iter_messages(dialog.id, filter=InputMessagesFilterPhotoVideo):
            if message.media:
                task = asyncio.create_task(_process_message(client, message, dialog.id, save_dir, sem))
                tasks.add(task)
                await _wait_tasks(MAX_TASKS)

        print("[*] Processing documents (images/videos)...")
        async for message in client.iter_messages(dialog.id, filter=InputMessagesFilterDocument):
            if message.file and message.file.mime_type:
                mime = message.file.mime_type.lower()
                if mime.startswith('image/') or mime.startswith('video/'):
                    task = asyncio.create_task(_process_message(client, message, dialog.id, save_dir, sem))
                    tasks.add(task)
                    await _wait_tasks(MAX_TASKS)

        # Wait for all remaining tasks to complete
        await _wait_tasks(0)

        # Print summary from database
        summary = await db.get_chat_summary(dialog.id)
        success_count = summary.get('success', 0)
        failure_count = summary.get('failure', 0)
        print(f"\n[+] Finished '{dialog.title}'. Total Success: {success_count}, Failures: {failure_count}\n")
    except Exception as e:
        print(f"[-] Fatal error during chat download: {e}\n")

async def show_chat_list_paginated(client, initial_search=""):
    """Display a paginated list of chats. Navigate with arrow keys / jk,
    press the number shown to select a chat, or use n/p for pages.
    """
    try:
        print("\n[+] Fetching dialogs...")
        all_dialogs = await client.get_dialogs()

        if not all_dialogs:
            print("[-] No chats found.\n")
            return

        search_query = initial_search
        current_page = 0
        PAGE_SIZE = 10

        while True:
            dialogs = (
                [d for d in all_dialogs if search_query.lower() in (d.title or "Unknown").lower()]
                if search_query else all_dialogs
            )

            total_pages = max(1, (len(dialogs) + PAGE_SIZE - 1) // PAGE_SIZE)

            if current_page >= total_pages:
                current_page = total_pages - 1
            if current_page < 0:
                current_page = 0

            start_idx = current_page * PAGE_SIZE
            page_dialogs = dialogs[start_idx : start_idx + PAGE_SIZE]

            header = f"--- Chats (Page {current_page + 1}/{total_pages})"
            if search_query:
                header += f" [Search: '{search_query}']"
            header += " ---"

            page_choices = []
            page_shortcuts = []
            for i, dialog in enumerate(page_dialogs):
                title = dialog.title or "Unknown"
                if dialog.is_user and getattr(dialog.entity, "deleted", False):
                    title = f"Deleted Account (ID: {dialog.id})"
                page_choices.append(questionary.Choice(title, dialog))
                # Number 1-9,0 to match top keyboard row
                page_shortcuts.append(str((i + 1) % 10))

            if not page_choices:
                page_choices.append(questionary.Choice("(No chats found)", "__empty__"))
                page_shortcuts.append("")

            action = await menu_select(
                header,
                choices=page_choices,
                shortcuts=page_shortcuts,
                page_nav={"has_prev": current_page > 0, "has_next": current_page < total_pages - 1},
                settings_line=True,
            )

            if action == "__next__":
                current_page += 1
            elif action == "__prev__":
                current_page -= 1
            elif action == "__settings__":
                res = await handle_settings(client, is_auth=True, has_creds=True)
                if res == "break":
                    return "break"
                # Normal back from Settings: loop continues, preserving page/search
            elif action == "__back__":
                break
            elif action == "__empty__":
                pass
            else:
                # A dialog object was selected
                dialog = action
                confirm = await ask_confirm(f"Download media from '{dialog.title or 'Unknown'}'?")
                if confirm:
                    await download_chat_media(client, dialog)
    except Exception as e:
        print(f"[-] Failed to fetch dialogs: {e}\n")

async def download_deleted_accounts_media(client):
    print("\n[*] Scanning for deleted account chats...")
    all_dialogs = await client.get_dialogs()
    deleted_dialogs = [
        d for d in all_dialogs
        if d.is_user and getattr(d.entity, "deleted", False)
    ]

    if not deleted_dialogs:
        print("[-] No deleted account chats found.\n")
        return

    print(f"[+] Found {len(deleted_dialogs)} deleted account chat(s).")
    for dialog in deleted_dialogs:
        await download_chat_media(client, dialog)
    print("[+] Finished downloading from all deleted account chats.\n")

async def handle_logout(client):
    confirm = await ask_confirm("Are you sure you want to log out?")
    if confirm:
        await client.log_out()
        print("[+] Logged out successfully!\n")

async def handle_settings(client=None, is_auth=False, has_creds=True):
    while True:
        current_dir = config.get_download_dir()
        choices = [
            questionary.Choice(f"Change Download Directory (Current: {current_dir})", "change_dir"),
        ]
        shortcuts = ["d"]
        if has_creds:
            choices.append(questionary.Choice("Clear Telegram App Credentials", "clear_creds"))
            shortcuts.append("c")

        action = await menu_select(
            "Settings Menu",
            choices=choices,
            shortcuts=shortcuts,
        )

        if action == "change_dir":
            new_dir = await ask_text("Enter new download directory path:")
            if new_dir:
                expanded_dir = os.path.expanduser(new_dir)
                config.set_download_dir(expanded_dir)
                print(f"[+] Download directory updated to: {expanded_dir}\n")
        elif action == "clear_creds":
            if client:
                await client.disconnect()
            config.clear_credentials()
            print("[+] Credentials cleared.\n")
            return "break"
        elif action == "__back__":
            break

async def telegram_loop():
    while True:
        api_id, api_hash = config.get_credentials()
        
        if not api_id or not api_hash:
            action = await menu_select(
                "ChronoChat - Telegram (No Credentials)",
                choices=[
                    questionary.Choice("Set App Credentials", "set_creds"),
                ],
                shortcuts=["c"],
                settings_line=True,
            )
            
            if action == "set_creds":
                await prompt_credentials()
            elif action in ("settings", "__settings__"):
                res = await handle_settings(None, is_auth=False, has_creds=False)
                if res == "break":
                    continue
            elif action == "__back__":
                break
        else:
            print("[*] Connecting to Telegram...")
            client = None
            try:
                client = await auth.get_client(api_id, api_hash)
            except Exception as e:
                action = await menu_select(
                    f"[-] Failed to initialize client. Your credentials might be invalid or network is down.\n    Error: {e}",
                    choices=[],
                    shortcuts=[],
                    settings_line=True,
                )
                if action in ("settings", "__settings__"):
                    res = await handle_settings(None, is_auth=False, has_creds=True)
                    if res == "break":
                        continue
                elif action == "__back__":
                    break

            try:
                is_auth = await auth.is_authorized(client)
                
                if not is_auth:
                    action = await menu_select(
                        "ChronoChat - Telegram (Not Logged In)",
                        choices=[
                            questionary.Choice("Log In", "login"),
                        ],
                        shortcuts=["i"],
                        settings_line=True,
                    )
                    
                    if action == "login":
                        await handle_login(client)
                    elif action in ("settings", "__settings__"):
                        res = await handle_settings(client, is_auth=False, has_creds=True)
                        if res == "break":
                            continue
                    elif action == "__back__":
                        break
                else:
                    me = await client.get_me()
                    action = await menu_select(
                        f"ChronoChat - Telegram ({me.first_name})",
                        choices=[
                            questionary.Choice("Show all chats", "show_chats"),
                            questionary.Choice("Search", "search"),
                            questionary.Choice("Download all media", "download_all"),
                            questionary.Choice("Download from Deleted Accounts", "download_deleted"),
                            questionary.Choice("Log Out", "logout"),
                        ],
                        shortcuts=["a", "f", "d", "x", "o"],
                        settings_line=True,
                    )

                    res = None
                    if action == "show_chats":
                        res = await show_chat_list_paginated(client)
                    elif action == "search":
                        query = await ask_text("Enter search query:")
                        if query:
                            res = await show_chat_list_paginated(client, initial_search=query)
                    elif action == "download_all":
                        print("[*] Downloading media from all chats...")
                        dialogs = await client.get_dialogs()
                        for dlg in dialogs:
                            await download_chat_media(client, dlg)
                        print("[+] Finished downloading all chats.")
                    elif action == "download_deleted":
                        await download_deleted_accounts_media(client)
                    elif action == "logout":
                        await handle_logout(client)
                        continue
                    elif action in ("settings", "__settings__"):
                        res = await handle_settings(client, is_auth=True, has_creds=True)
                    elif action == "__back__":
                        break

                    if res == "break":
                        continue
            finally:
                if client:
                    await client.disconnect()


async def main_loop():
    print("Welcome to ChronoChat Terminal Menu!")
    while True:
        action = await menu_select(
            "ChronoChat",
            choices=[
                questionary.Choice("Telegram", "telegram"),
                questionary.Choice("Signal", "signal"),
            ],
            shortcuts=["t", "s"],
            settings_line=True,
        )

        if action == "telegram":
            await telegram_loop()
        elif action == "signal":
            from functools import partial
            api_id, api_hash = config.get_credentials()
            has_creds = bool(api_id and api_hash)
            await signal_backup.signal_backup_menu(
                settings_handler=partial(handle_settings, None, is_auth=False, has_creds=has_creds)
            )
        elif action in ("settings", "__settings__"):
            api_id, api_hash = config.get_credentials()
            has_creds = bool(api_id and api_hash)
            res = await handle_settings(None, is_auth=False, has_creds=has_creds)
            if res == "break":
                continue
        elif action == "__back__":
            break
