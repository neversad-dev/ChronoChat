# ChronoChat
[![GitHub license](https://img.shields.io/github/license/neversad-dev/ChronoChat)](LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/neversad-dev/ChronoChat)](https://github.com/neversad-dev/ChronoChat/issues)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org)

A Python application for interacting with messaging platforms via a terminal UI. Download media from your chats and automatically correct timestamps so they appear correctly in photo libraries.

## Features
- **Telegram**: Download all media from chats with resume support via an embedded SQLite database. Corrects timestamps using message date, filename patterns, and EXIF data.
- **Signal Android Backup Import**: Import media from Signal backups or extracted folders, including decrypted JSON exports.
- **Concurrent Media Downloading**: Uses asynchronous semaphores to download multiple files simultaneously while respecting rate limits.
- **Resilient State Tracking**: Maintains a built-in SQLite database (`~/.config/chronochat/downloads.db`) to track successful downloads. You can safely interrupt a large download with `Ctrl+C` and resume later without re-downloading files.
- **Vim-style navigation**: Navigate menus with `hjkl` keys and letter shortcuts.
- **Configurable download directory** stored in your local config.

## Prerequisites

- [Nix](https://nixos.org/download) package manager with [Flakes enabled](https://nixos.wiki/wiki/Flakes#Enable_flakes).

## Credentials Setup (Telegram)

To use the Telegram API, you must register your application to obtain an `api_id` and `api_hash`.

1. Go to [my.telegram.org](https://my.telegram.org/) and log in with your phone number.
2. Click on **API development tools**.
3. Fill out the application form:
   - **App title**: Choose any name.
   - **Short name**: Choose any short alphanumeric name.
4. Click **Create application**.
5. Keep your **App api_id** and **App api_hash** values handy.

## Usage

### Run the Application

Launch ChronoChat directly from GitHub:
```bash
nix run github:neversad-dev/ChronoChat
```

**Local Development Run:**
```bash
nix run .#
```

**Development Shell:**
```bash
nix develop
python3 main.py
```

### Navigation

All menus use vim-style keybindings:

| Key | Action |
|-----|--------|
| `↑` / `k` | Move selection up |
| `↓` / `j` | Move selection down |
| `←` / `h` | Go back to previous menu |
| `→` / `l` or `Enter` | Select current item |
| Letter shortcut (`[t]`, `[s]`, etc.) | Jump directly to item |
| `.` | Open Settings (from any screen) |
| `q` | Quit program immediately |

Text prompts show `[Ctrl+C] Cancel` at the bottom. Pressing `Ctrl+C` at any prompt safely cancels and returns to the menu.

### Menu Structure

- **Telegram**
  - Set API Credentials (if not configured)
  - Log In (if not authenticated)
  - **Show all chats** — browse paginated chat list
  - **Search** — filter chats by name
  - **Download all media** — download from every chat
  - **Download from Deleted Accounts** — find and download from deleted account chats
- **Signal Import Source**
  - Import from `.backup` file
  - Import from extracted folder (supports JSON exports and raw media folders)
- **Settings**
  - Change Download Directory
  - Clear Telegram App Credentials
  - Log Out

## How Timestamp Correction Works

Media files are processed to find the earliest reasonable date from:
1. **Message date** from Telegram (converted to local time)
2. **Filename date** (patterns like `IMG_YYYYMMDD_HHMMSS` or WhatsApp format)
3. **Existing EXIF metadata**

The earliest valid date wins. The file's modification time is always updated. If the best date differs from existing EXIF by more than one hour, the EXIF data is rewritten as well.

## Signal Backup Import

### From `.backup` file
Requires the encrypted `.backup` file from Signal (Settings → Chats → Backups) plus the 30-digit passphrase. The tool uses `signalbackup-tools` to extract attachments, then applies timestamp correction.

### From extracted folder
Supports:
- **Decrypted JSON export** (`main.jsonl` + `files/` directory) — parsed for message timestamps
- **Raw extracted media** — metadata is inferred from file modification time

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
