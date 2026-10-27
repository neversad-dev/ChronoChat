import asyncio
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import questionary

import config
import metadata

_MEDIA_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic',
    '.mp4', '.mov', '.webm', '.3gp', '.avi', '.mkv', '.m4v'
}


def _is_media_file(path):
    return Path(path).suffix.lower() in _MEDIA_EXTENSIONS


async def _prompt_backup_path():
    while True:
        backup_path = await questionary.text("Path to Signal backup file (.backup)").ask_async()
        if backup_path is None:
            return None
        if backup_path and os.path.isfile(backup_path):
            return backup_path
        print("[-] Invalid path. Please enter a valid file path.")


async def _prompt_passphrase():
    while True:
        raw = await questionary.password("Signal 30-digit backup passphrase (spaces/hyphens OK)").ask_async()
        if raw is None:
            return None
        cleaned = ''.join(c for c in raw if c.isdigit())
        if len(cleaned) == 30:
            return cleaned
        print(f"[-] Passphrase must contain exactly 30 digits (got {len(cleaned)}).")


async def _prompt_folder_path():
    while True:
        folder = await questionary.text("Path to extracted Signal folder (e.g. containing files/)").ask_async()
        if folder is None:
            return None
        expanded = os.path.expanduser(folder)
        if os.path.isdir(expanded):
            return expanded
        print("[-] Invalid folder. Please enter a valid directory path.")


def _extract_media(backup_path, passphrase, output_dir):
    try:
        subprocess.run(
            ['signalbackup-tools', backup_path, passphrase, '--dumpmedia', output_dir],
            capture_output=True,
            check=True
        )
    except FileNotFoundError:
        print("[-] signalbackup-tools not found. Please run inside the Nix devShell (nix develop).")
        raise


async def _adjust_single_file(file_path, semaphore):
    async with semaphore:
        mtime = os.path.getmtime(file_path)
        mtime_dt = datetime.fromtimestamp(mtime)
        metadata.adjust_media_metadata(file_path, mtime_dt)


async def _process_extracted_media(extracted_dir, target_base_dir):
    signal_dir = target_base_dir / "signal"
    signal_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    processed = 0
    skipped = 0
    total_in_dir = 0
    semaphore = asyncio.Semaphore(10)

    for root, _, files in os.walk(extracted_dir):
        for filename in files:
            total_in_dir += 1
            src = Path(root) / filename
            if not _is_media_file(src):
                continue

            rel_path = src.relative_to(extracted_dir)
            dest_path = signal_dir / rel_path

            if dest_path.exists():
                skipped += 1
                continue

            os.makedirs(dest_path.parent, exist_ok=True)
            shutil.copy2(src, dest_path)

            task = asyncio.create_task(_adjust_single_file(dest_path, semaphore))
            tasks.append(task)

            if len(tasks) >= 50:
                await asyncio.gather(*tasks)
                processed += len(tasks)
                tasks = []

    if tasks:
        await asyncio.gather(*tasks)
        processed += len(tasks)

    print(f"[+] Processed: {processed}")
    print(f"[*] Skipped (already exist): {skipped}")

    if processed == 0 and total_in_dir > 0:
        _show_blob_diagnostic(extracted_dir, total_in_dir)
        return False

    return True


def _show_blob_diagnostic(extracted_dir, total_in_dir):
    blob_count = sum(
        1 for _, _, files in os.walk(extracted_dir) for f in files if '.' not in f
    )
    if blob_count > total_in_dir * 0.8:
        print("")
        print("[!] Detected Signal's new backup-v2 format (raw attachment blobs).")
        print("    These files are unidentifiable without the internal database.")
        print("    signalbackup-tools does not yet support this format.")
        print("    Track progress: https://github.com/bepaald/signalbackup-tools/issues/382")
        print("")
        print("    Options:")
        print("      1) Use the encrypted .backup file from Signal → Settings → Chats → Backups")
        print("      2) Wait for signalbackup-tools to support backup-v2")
        print("      3) Re-export to a format with intact filenames (if available in your exporter)")
    else:
        print("")
        print("[!] No supported media files found.")
        print("    Supported: jpg/jpeg, png, gif, bmp, webp, heic, mp4, mov, webm, 3gp, avi, mkv, m4v")


async def _import_from_backup():
    print("[*] You need the .backup file from your phone and the 30-digit passphrase.")

    backup_path = await _prompt_backup_path()
    if backup_path is None:
        return
    passphrase = await _prompt_passphrase()
    if passphrase is None:
        return

    target_dir = Path(config.get_download_dir())
    target_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="chronochat_signal_") as tmpdir:
        print("[*] Extracting media with signalbackup-tools...")
        try:
            _extract_media(backup_path, passphrase, tmpdir)
        except Exception:
            print("[-] Extraction failed.")
            return

        print("[*] Copying and fixing metadata...")
        await _process_extracted_media(tmpdir, target_dir)
        print("[+] Done.")


async def _import_from_folder():
    print("[*] Import from an already-extracted Signal backup folder.")

    folder = await _prompt_folder_path()
    if folder is None:
        return

    target_dir = Path(config.get_download_dir())
    target_dir.mkdir(parents=True, exist_ok=True)

    print("[*] Copying and fixing metadata...")
    success = await _process_extracted_media(folder, target_dir)
    if success:
        print("[+] Done.")
    else:
        print("[-] Import failed. See diagnostic above.")


async def signal_backup_menu():
    print("[*] Signal Android Backup Import")

    action = await questionary.select(
        "Signal Import Source",
        choices=[
            questionary.Choice("Import from .backup file", "from_backup"),
            questionary.Choice("Import from extracted folder", "from_folder"),
            questionary.Choice("Back", "back"),
        ]
    ).ask_async()

    if action == "back" or action is None:
        return
    elif action == "from_backup":
        await _import_from_backup()
    elif action == "from_folder":
        await _import_from_folder()
