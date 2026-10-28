import os
import re
import subprocess
from datetime import datetime

def extract_date_from_filename(filename):
    """
    Tries to extract a date from common filename patterns:
    - IMG_YYYYMMDD_HHMMSS
    - VID_YYYYMMDD_HHMMSS
    - WhatsApp Image YYYY-MM-DD at HH.MM.SS
    - YYYYMMDD-HHMMSS
    Returns a datetime object (naive, assumed local) or None.
    """
    # Pattern: YYYYMMDD_HHMMSS or YYYYMMDD-HHMMSS
    match = re.search(r'(\d{4})(\d{2})(\d{2})[_.-](\d{2})(\d{2})(\d{2})', filename)
    if match:
        try:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass
            
    # Pattern: YYYY-MM-DD at HH.MM.SS (WhatsApp)
    match = re.search(r'(\d{4})-(\d{2})-(\d{2}) at (\d{2})\.(\d{2})\.(\d{2})', filename)
    if match:
        try:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second)
        except ValueError:
            pass
            
    return None

def get_exif_date(file_path):
    """
    Reads CreateDate or DateTimeOriginal using exiftool.
    Returns a naive datetime object or None.
    """
    try:
        # -s3 gives just the value. We check DateTimeOriginal then CreateDate
        result = subprocess.run(
            ['exiftool', '-DateTimeOriginal', '-CreateDate', '-s3', file_path],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if output:
            first_date_str = output.split('\n')[0].strip()
            if len(first_date_str) >= 19:
                try:
                    return datetime.strptime(first_date_str[:19], "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    pass
    except Exception:
        pass
    return None

def _is_reasonable_date(dt):
    if not dt:
        return False
    now = datetime.now()
    return 1990 <= dt.year <= now.year + 1

def adjust_media_metadata(file_path, message_date):
    """
    Adjusts the metadata of the media file to the earliest valid date among:
    - message_date (from Telegram, UTC aware)
    - filename date
    - EXIF date
    """
    filename = os.path.basename(file_path)
    candidates = []

    # 1. Message Date
    if message_date is not None:
        msg_date_local = message_date.astimezone()
        msg_date_naive = msg_date_local.replace(tzinfo=None)
        if _is_reasonable_date(msg_date_naive):
            candidates.append(msg_date_naive)

    # 2. Filename Date
    fn_date = extract_date_from_filename(filename)
    if _is_reasonable_date(fn_date):
        candidates.append(fn_date)

    # 3. EXIF Date
    exif_date = get_exif_date(file_path)
    if _is_reasonable_date(exif_date):
        candidates.append(exif_date)

    if not candidates:
        print(f"[-] No reasonable date found for '{filename}', skipping metadata adjustment.")
        return

    best_date = min(candidates)

    needs_update = True
    if exif_date and _is_reasonable_date(exif_date):
        diff = abs((exif_date - best_date).total_seconds())
        if diff <= 3600:
            needs_update = False

    if needs_update:
        print(f"[*] Adjusting metadata for '{filename}' to {best_date.strftime('%Y-%m-%d %H:%M:%S')}")
        date_str = best_date.strftime("%Y:%m:%d %H:%M:%S")
        try:
            subprocess.run(
                [
                    'exiftool',
                    f'-AllDates={date_str}',
                    f'-CreationDate={date_str}',
                    '-overwrite_original',
                    file_path
                ],
                capture_output=True,
                check=True,
                timeout=30
            )
        except Exception as e:
            print(f"[-] Failed to update EXIF for {filename}: {e}")

    # Always update file modification time as a fallback
    timestamp = best_date.timestamp()
    try:
        os.utime(file_path, (timestamp, timestamp))
    except Exception as e:
        print(f"[-] Failed to update file time for {filename}: {e}")
