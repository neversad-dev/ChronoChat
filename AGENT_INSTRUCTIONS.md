# ChronoChat — Agent Implementation Instructions

## Goal

Refactor the existing CLI menu so that Telegram is a nested sub-tree, add a parallel Signal sub-tree, harden metadata date
selection against corrupted/zero/future dates, and implement Signal Android backup import.

## Branch Policy

Create and work on a **new branch** `feature/signal-backup`. Do NOT commit to `main`.

## A. Metadata Hardening (`metadata.py`)

Edit `metadata.py`. After `get_exif_date()`, add a helper:

```python
def _is_reasonable_date(dt):
    if not dt:
        return False
    now = datetime.now()
    return 1990 <= dt.year <= now.year + 1
```

Rewrite adjust_media_metadata(file_path, message_date) with this logic:

1.  Gather up to three candidate datetimes:
    - message_date (if provided and not None): convert to local via .astimezone(), strip tzinfo, validate with
      _is_reasonable_date().
    - extract_date_from_filename(filename): validate with _is_reasonable_date().
    - get_exif_date(file_path): validate with _is_reasonable_date().
2.  If zero candidates are valid, print:
    [-] No reasonable date found for '<filename>', skipping metadata adjustment.
    and return early. Do not write anything.
3.  Otherwise best_date = min(candidates). This is the earliest valid date, which handles photos shot long before they were
    shared.
4.  Determine if EXIF needs rewriting:
    - needs_update = True by default.
    - If EXIF date exists and is reasonable, compute diff = abs((exif_date - best_date).total_seconds()).
    - If diff <= 3600, set needs_update = False.
5.  If needs_update, run exiftool with timeout=30:
    ```python
      subprocess.run(
          ['exiftool', f'-AllDates={date_str}', f'-CreationDate={date_str}', '-overwrite_original', file_path],
          capture_output=True, check=True, timeout=30
      )
    ```
6.  Always call os.utime(file_path, (timestamp, timestamp)) with best_date.timestamp().

### Behavioral notes

- Do not touch the existing extract_date_from_filename() or get_exif_date() functions.
- _is_reasonable_date must reject the Unix epoch (1970), year 0, and wildly futuristic years.

────────────────────────────────────────────────────────────────────────────────

B. CLI Menu Refactor (cli.py)

Refactor main_loop() into three async functions.

### 1. telegram_loop()

Move the entire existing while True: body of main_loop() into a new async def telegram_loop(): function. Change the prompt
titles to reflect the nested context:

┌───────────────────────────────┬────────────────────────────────────────┐
│ Old Title │ New Title │
├───────────────────────────────┼────────────────────────────────────────┤
│ ChronoChat - No Credentials │ ChronoChat - Telegram (No Credentials) │
├───────────────────────────────┼────────────────────────────────────────┤
│ ChronoChat - Not Logged In │ ChronoChat - Telegram (Not Logged In) │
├───────────────────────────────┼────────────────────────────────────────┤
│ ChronoChat - Logged In (Name) │ ChronoChat - Telegram (Name) │
└───────────────────────────────┴────────────────────────────────────────┘

Change every "Exit" choice in the Telegram sub-tree to "Back". The action value should be "back" instead of "exit", and the
branch should break the inner telegram_loop() rather than the outer main_loop().

The Error Menu inside the Telegram connect block should also use "Back" instead of "Exit".

### 2. signal_loop()

Create a new placeholder function:

```python
  async def signal_loop():
      while True:
          action = await questionary.select(
              "ChronoChat - Signal",
              choices=[
                  questionary.Choice("Import from Android Backup", "import_backup"),
                  questionary.Choice("Back", "back"),
              ]
          ).ask_async()

          if action == "import_backup":
              # Will call signal_backup.signal_backup_menu() once implemented
              print("[*] Signal backup support coming soon.")
          else:
              break
```

### 3. New main_loop()

Replace the original main_loop() with a top-level dispatcher:

```python
  async def main_loop():
      print("Welcome to ChronoChat Terminal Menu!")
      while True:
          action = await questionary.select(
              "ChronoChat",
              choices=[
                  questionary.Choice("Telegram", "telegram"),
                  questionary.Choice("Signal", "signal"),
                  questionary.Choice("Settings", "settings"),
                  questionary.Choice("Exit", "exit")
              ]
          ).ask_async()

          if action == "telegram":
              await telegram_loop()
          elif action == "signal":
              await signal_loop()
          elif action == "settings":
              api_id, api_hash = config.get_credentials()
              has_creds = bool(api_id and api_hash)
              res = await handle_settings(None, is_auth=False, has_creds=has_creds)
              if res == "break":
                  continue
          else:
              break
```

### Verification

After editing, python3 -m py_compile cli.py must produce no output.

────────────────────────────────────────────────────────────────────────────────

C. Signal Backup Import (signal_backup.py)

Create a new module signal_backup.py with the following public API and private helpers.

### Imports required

```python
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
```

### _is_media_file(path)

Return True for extensions:

```python
  {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic',
   '.mp4', '.mov', '.webm', '.3gp', '.avi', '.mkv', '.m4v'}
```

Case-insensitive comparison.

### _prompt_backup_path()

Async questionary path prompt:

```
  "Path to Signal backup file (.backup)"
```

Validate with os.path.isfile(). Loop until valid.

### _prompt_passphrase()

Async questionary password prompt:

```
  "Signal 30-digit backup passphrase (spaces/hyphens OK)"
```

Strip all non-digits, validate len == 30. Loop until valid. Return the cleaned 30-digit string.

### _extract_media(backup_path, passphrase, output_dir)

Run:

```bash
  signalbackup-tools <backup_path> <passphrase> --dumpmedia <output_dir>
```

Use subprocess.run(..., check=True). If FileNotFoundError, print:

```
  [-] signalbackup-tools not found. Please run inside the Nix devShell (nix develop).
```

and re-raise so the caller knows extraction failed.

### _adjust_single_file(file_path, semaphore)

Async helper. Acquire the semaphore, then:

1.  Read os.path.getmtime(file_path).
2.  Convert to datetime.fromtimestamp(mtime).
3.  Call metadata.adjust_media_metadata(file_path, message_date).
4.  Release semaphore.

### _process_extracted_media(extracted_dir, target_base_dir)

1.  Ensure target_base_dir / "signal" exists.
2.  Walk extracted_dir. For every file where _is_media_file() is true:
    - Compute relative path from extracted_dir.
    - Derive dest_path = target_base_dir / "signal" / relative_path.
    - If dest_path exists, skip (this enables safe resume).
    - os.makedirs(dest_path.parent, exist_ok=True).
    - shutil.copy2(src, dest_path) — this also copies mtime.
    - Spawn _adjust_single_file(dest_path, semaphore) as an asyncio task.
3.  Use asyncio.Semaphore(10) to limit concurrent exiftool calls.
4.  Every 50 tasks, await asyncio.gather(*batch) to avoid unbounded memory growth.
5.  After the walk, gather any remaining tasks.
6.  Print:
    ```
      [+] Processed: {processed}
      [*] Skipped (already exist): {skipped}
    ```

### signal_backup_menu()

Public entrypoint orchestrating the flow:

```python
  async def signal_backup_menu():
      print("[*] Signal Android Backup Import")
      print("[*] You need the .backup file from your phone and the 30-digit passphrase.")

      backup_path = await _prompt_backup_path()
      passphrase = await _prompt_passphrase()

      target_dir = Path(config.get_download_dir()) / "signal"
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
```

────────────────────────────────────────────────────────────────────────────────

D. Nix Flake Dependency (flake.nix)

Add pkgs.signalbackup-tools to both lists:

1.  packages.default.propagatedBuildInputs
2.  devShells.default.buildInputs

Make sure it appears alongside the other propagated inputs.

────────────────────────────────────────────────────────────────────────────────

E. Module Registration (pyproject.toml)

Add "signal_backup" to the py-modules list under [tool.setuptools].

────────────────────────────────────────────────────────────────────────────────

F. CLI Integration (cli.py)

At the top of cli.py, add:

```python
  import signal_backup
```

Inside signal_loop(), replace the placeholder print with:

```python
  if action == "import_backup":
      await signal_backup.signal_backup_menu()
```

────────────────────────────────────────────────────────────────────────────────

G. Final Verification

Run:

```bash
  python3 -m py_compile cli.py auth.py config.py metadata.py main.py db.py signal_backup.py
```

Must produce zero output.

Then commit with a message like:

```
  feat: Signal Android backup import; refactor Telegram/Signal menus; harden metadata dates
```

Push the feature/signal-backup branch. Do NOT merge into improvements or main.

────────────────────────────────────────────────────────────────────────────────

Important Behavioral Rules

1.  Signal is fully independent of Telegram. The user can run Signal import even if Telegram credentials are missing.
2.  Do not touch db.py from signal_backup.py. Signal resume is file-system based (skip if exists), not SQLite based.
3.  Preserve conversation subfolders. signalbackup-tools dumps media into conversation directories; keep that tree under
    ~/Downloads/chronochat/signal/.
4.  All dates sanity-checked. If signalbackup-tools produces an mtime of 1970 (unlikely, but guard anyway),
    _is_reasonable_date in adjust_media_metadata will skip it rather than corrupting the file.
5.  Use questionary for all prompts and [+] / [-] / [*] prefixes for status prints to match existing UI style.
6.  Do not modify db.py, auth.py, config.py, or metadata.py beyond the specific changes listed above.

```

```
