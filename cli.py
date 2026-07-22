import questionary
import config
import auth
from telethon import errors

async def prompt_credentials():
    print("\n[!] Please enter your Telegram API credentials.")
    print("[!] Get them from https://my.telegram.org/ \n")
    
    api_id_str = await questionary.text("Enter your App api_id (integer):").ask_async()
    if not api_id_str or not api_id_str.isdigit():
        print("[-] Invalid api_id. It must be an integer.")
        return

    api_hash = await questionary.text("Enter your App api_hash (string):").ask_async()
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
    phone = await questionary.text("Enter your phone number (e.g. +1234567890):").ask_async()
    if not phone: return
    
    try:
        await client.send_code_request(phone)
        code = await questionary.text("Enter the code you received:").ask_async()
        
        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            password = await questionary.password("Two-step verification is enabled. Enter your password:").ask_async()
            await client.sign_in(password=password)
            
        me = await client.get_me()
        print(f"[+] Logged in successfully as {me.first_name}!\n")
    except Exception as e:
        print(f"[-] Login failed: {e}\n")

async def show_chat_list(client):
    try:
        print("\n[+] Fetching dialogs...")
        all_dialogs = await client.get_dialogs()
        
        if not all_dialogs:
            print("[-] No chats found.\n")
            return

        search_query = ""
        current_page = 0
        PAGE_SIZE = 10
        
        while True:
            if search_query:
                dialogs = [d for d in all_dialogs if search_query.lower() in (d.title or "Unknown").lower()]
            else:
                dialogs = all_dialogs

            total_pages = max(1, (len(dialogs) + PAGE_SIZE - 1) // PAGE_SIZE)
            
            # Ensure current_page is valid
            if current_page >= total_pages:
                current_page = total_pages - 1
            if current_page < 0:
                current_page = 0
                
            start_idx = current_page * PAGE_SIZE
            end_idx = start_idx + PAGE_SIZE
            page_dialogs = dialogs[start_idx:end_idx]
            
            header = f"\n--- Chats (Page {current_page + 1}/{total_pages})"
            if search_query:
                header += f" [Search: '{search_query}']"
            header += " ---"
            print(header)
            
            if not page_dialogs:
                print("[-] No chats match your search.")
            else:
                for i, dialog in enumerate(page_dialogs):
                    title = dialog.title or "Unknown"
                    print(f"{start_idx + i + 1}. {title}")
            print("-------------------------")
                
            choices = []
            if current_page < total_pages - 1:
                choices.append(questionary.Choice("Next Page", "next"))
            if current_page > 0:
                choices.append(questionary.Choice("Previous Page", "prev"))
                
            choices.append(questionary.Choice("Search", "search"))
            if search_query:
                choices.append(questionary.Choice("Clear Search", "clear_search"))
                
            choices.append(questionary.Choice("Quit List", "quit"))
            
            action = await questionary.select(
                "Select action:",
                choices=choices
            ).ask_async()
            
            if action == "prev":
                current_page -= 1
            elif action == "next":
                current_page += 1
            elif action == "search":
                query = await questionary.text("Enter search query:").ask_async()
                if query:
                    search_query = query
                    current_page = 0
            elif action == "clear_search":
                search_query = ""
                current_page = 0
            else:
                print()
                break
                
    except Exception as e:
        print(f"[-] Failed to fetch dialogs: {e}\n")

async def handle_logout(client):
    confirm = await questionary.confirm("Are you sure you want to log out?").ask_async()
    if confirm:
        await client.log_out()
        print("[+] Logged out successfully!\n")

async def main_loop():
    print("Welcome to ChronoChat Terminal Menu!")
    while True:
        api_id, api_hash = config.get_credentials()
        
        if not api_id or not api_hash:
            action = await questionary.select(
                "ChronoChat - No Credentials",
                choices=[
                    questionary.Choice("Set App Credentials", "set_creds"),
                    questionary.Choice("Exit", "exit")
                ]
            ).ask_async()
            
            if action == "set_creds":
                await prompt_credentials()
            else:
                break
        else:
            print("[*] Connecting to Telegram...")
            try:
                client = await auth.get_client(api_id, api_hash)
            except Exception as e:
                print(f"[-] Failed to initialize client. Your credentials might be invalid or network is down. Error: {e}")
                action = await questionary.select(
                    "Error Menu",
                    choices=[
                        questionary.Choice("Clear App Credentials", "clear_creds"),
                        questionary.Choice("Exit", "exit")
                    ]
                ).ask_async()
                if action == "clear_creds":
                    config.clear_credentials()
                    print("[+] Credentials cleared.\n")
                    continue
                else:
                    break

            try:
                is_auth = await auth.is_authorized(client)
                
                if not is_auth:
                    action = await questionary.select(
                        "ChronoChat - Not Logged In",
                        choices=[
                            questionary.Choice("Log In", "login"),
                            questionary.Choice("Clear App Credentials", "clear_creds"),
                            questionary.Choice("Exit", "exit")
                        ]
                    ).ask_async()
                    
                    if action == "login":
                        await handle_login(client)
                    elif action == "clear_creds":
                        await client.disconnect()
                        client = None
                        config.clear_credentials()
                        print("[+] Credentials cleared.\n")
                    else:
                        break
                else:
                    me = await client.get_me()
                    action = await questionary.select(
                        f"ChronoChat - Logged In ({me.first_name})",
                        choices=[
                            questionary.Choice("Show Chat List", "show_chats"),
                            questionary.Choice("Log Out", "logout"),
                            questionary.Choice("Exit", "exit")
                        ]
                    ).ask_async()
                    
                    if action == "show_chats":
                        await show_chat_list(client)
                    elif action == "logout":
                        await handle_logout(client)
                    else:
                        break
            finally:
                if client:
                    await client.disconnect()
