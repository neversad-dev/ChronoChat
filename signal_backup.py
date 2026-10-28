import asyncio
import base64
import binascii
import json
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

_MIME_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/bmp': '.bmp',
    'image/webp': '.webp',
    'image/heic': '.heic',
    'video/mp4': '.mp4',
    'video/quicktime': '.mov',
    'video/webm': '.webm',
    'video/3gpp': '.3gp',
    'video/x-msvideo': '.avi',
    'video/x-matroska': '.mkv',
    'video/x-m4v': '.m4v',
}


def _resolve_dest_path(signal_dir, src, dest_name):
    """Find a destination path that avoids overwriting different content.

    Returns (dest_path, is_duplicate). If is_duplicate is True, src should be
    deleted (same file already preserved). Otherwise, copy src to dest_path.
    """
    dest_path = signal_dir / dest_name

    if not dest_path.exists():
        return dest_path, False

    if dest_path.stat().st_size == src.stat().st_size:
        return dest_path, True

    # Same name, different content — find collision-safe name
    base, ext = os.path.splitext(dest_name)
    counter = 1
    while True:
        alt_name = f"{base}_{counter}{ext}"
        alt_path = signal_dir / alt_name
        if not alt_path.exists():
            return alt_path, False
        if alt_path.stat().st_size == src.stat().st_size:
            return alt_path, True
        counter += 1


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


async def _adjust_single_file_with_timestamp(file_path, message_ts, semaphore):
    async with semaphore:
        if message_ts is not None:
            metadata.adjust_media_metadata(str(file_path), message_ts)
        else:
            mtime = os.path.getmtime(file_path)
            mtime_dt = datetime.fromtimestamp(mtime)
            metadata.adjust_media_metadata(str(file_path), mtime_dt)


def _parse_timestamp(ts):
    """Parse various timestamp formats."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000.0)
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            # Try parsing as integer string (milliseconds)
            try:
                num = int(ts)
                if num > 1e12:
                    return datetime.fromtimestamp(num / 1000.0)
                return datetime.fromtimestamp(num)
            except ValueError:
                pass
            # Try ISO format
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except ValueError:
                pass
    except (ValueError, OSError, OverflowError):
        pass
    return None


def _hash_to_path(export_dir, plaintext_hash_b64, content_type=None):
    """Convert base64 plaintextHash to actual file path in files/ directory."""
    try:
        decoded = base64.b64decode(plaintext_hash_b64)
        hex_hash = binascii.hexlify(decoded).decode()
        prefix = hex_hash[:2]

        ext = ''
        if content_type:
            mime_ext = _MIME_TO_EXT.get(content_type.lower())
            if mime_ext:
                ext = mime_ext

        if ext:
            candidate = os.path.join(export_dir, 'files', prefix, hex_hash + ext)
            if os.path.isfile(candidate):
                return candidate
        candidate = os.path.join(export_dir, 'files', prefix, hex_hash)
        if os.path.isfile(candidate):
            return candidate
    except Exception:
        pass
    return None


def _collect_attachments_from_jsonl(export_dir):
    """Parse main.jsonl and return list of (src_path, dest_name, timestamp)."""
    jsonl_path = os.path.join(export_dir, 'main.jsonl')
    attachments = []
    seen_paths = set()

    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Only process chat items
                chat_item = msg.get('chatItem')
                if not isinstance(chat_item, dict):
                    continue

                ts = None
                date_sent = chat_item.get('dateSent')
                if date_sent:
                    ts = _parse_timestamp(date_sent)

                standard_msg = chat_item.get('standardMessage', {})
                if not isinstance(standard_msg, dict):
                    continue

                atts = standard_msg.get('attachments', [])
                if isinstance(atts, dict):
                    atts = [atts]
                if not isinstance(atts, list):
                    continue

                for att in atts:
                    if not isinstance(att, dict):
                        continue
                    pointer = att.get('pointer', {})
                    if not isinstance(pointer, dict):
                        continue

                    locator = pointer.get('locatorInfo', {})
                    if not isinstance(locator, dict):
                        continue

                    hash_b64 = locator.get('plaintextHash')
                    if not hash_b64:
                        continue

                    content_type = pointer.get('contentType', '')
                    file_name = pointer.get('fileName', '')

                    src_path = _hash_to_path(export_dir, hash_b64, content_type)
                    if not src_path:
                        continue

                    if file_name:
                        dest_name = Path(file_name).name
                        if dest_name in ('', '.', '..'):
                            continue
                    else:
                        ext = _MIME_TO_EXT.get(content_type.lower(), '') if content_type else ''
                        dest_name = hash_b64.replace('/', '_').replace('=', '') + ext

                    if src_path in seen_paths:
                        continue
                    seen_paths.add(src_path)
                    attachments.append((src_path, dest_name, ts))

    except Exception:
        pass

    return attachments


async def _process_json_export(folder, target_dir):
    jsonl_path = Path(folder) / "main.jsonl"
    files_dir = Path(folder) / "files"

    if not jsonl_path.exists():
        print("[-] main.jsonl not found.")
        return False
    if not files_dir.exists():
        print("[-] files/ directory not found.")
        return False

    print("[*] Parsing main.jsonl for message timestamps and attachments...")
    attachments = _collect_attachments_from_jsonl(folder)

    if not attachments:
        print("[-] No attachments found in main.jsonl.")
        return False

    print(f"[*] Found {len(attachments)} attachment references.")

    signal_dir = target_dir / "signal"
    signal_dir.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(10)
    tasks = []
    processed = 0
    skipped = 0
    missing = 0

    removed = 0

    for src_path, dest_name, msg_ts in attachments:
        src = Path(src_path)
        if not src.exists():
            missing += 1
            continue

        if not _is_media_file(src):
            continue

        dest_path, is_dup = _resolve_dest_path(signal_dir, src, dest_name)
        if is_dup:
            try:
                os.remove(src)
                removed += 1
            except OSError:
                pass
            skipped += 1
            continue

        os.makedirs(dest_path.parent, exist_ok=True)
        shutil.copy2(src, dest_path)
        try:
            os.remove(src)
            removed += 1
        except OSError:
            pass

        task = asyncio.create_task(_adjust_single_file_with_timestamp(dest_path, msg_ts, semaphore))
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
    if removed:
        print(f"[*] Removed from source (disk space): {removed}")
    if missing:
        print(f"[*] Missing from disk: {missing}")
    return processed > 0


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

    # Detect if this is a decrypted JSON export
    jsonl_path = Path(folder) / "main.jsonl"
    if jsonl_path.exists():
        print("[*] Detected Signal decrypted JSON export (main.jsonl).")
        success = await _process_json_export(folder, target_dir)
        if success:
            print("[+] Done.")
        else:
            print("[-] JSON export import failed.")
        return

    # Otherwise, try regular extracted media folder
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
