# ChronoChat
[![GitHub license](https://img.shields.io/github/license/neversad-dev/ChronoChat)](LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/neversad-dev/ChronoChat)](https://github.com/neversad-dev/ChronoChat/issues)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org)

**Note:** This is a proof-of-concept and not a fully working application.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Credentials Setup](#credentials-setup)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [License](#license)

A Python application for interacting with the Telegram API using Telethon, managed via a multiplatform Nix dev shell. ChronoChat downloads media from your chats and automatically corrects timestamps so they appear correctly in Google Photos.

## Features
- Default download location `~/Downloads/chronochat` (configurable via Settings).
- Interactive terminal menu with Settings (change download directory, clear credentials, log out).
- Metadata correction for images **and videos** using bundled `exiftool` (earliest date from message, filename, or existing metadata).

## Prerequisites

- [Nix](https://nixos.org/download) package manager with [Flakes enabled](https://nixos.wiki/wiki/Flakes#Enable_flakes).

## Credentials Setup

To use the Telegram API, you must register your application to obtain an `api_id` and `api_hash`.

1. Go to [my.telegram.org](https://my.telegram.org/) and log in with your phone number associated with your Telegram account.
2. Click on **API development tools**.
3. Fill out the application form:
   - **App title**: Choose any name (e.g., `MyMediaDownloader`).
   - **Short name**: Choose any short alphanumeric name.
   - **URL/Description**: You can leave these blank or use placeholders.
4. Click **Create application**.
5. Once created, keep your **App api_id** and **App api_hash** values handy.

## Usage

### 1. Enter the Nix Development Environment

Start a shell containing Python and the required libraries (`telethon`, `python-dotenv`) by running:

```bash
nix develop
```

Upon entering, you will see a welcome message showing the active Python environment.

### 2. Run the Application

Once inside the development environment, execute the main script:

```bash
python3 main.py
```

Or run it directly from your host shell:

```bash
nix develop --command python3 main.py
```

### 3. Interactive Terminal Menu

ChronoChat now features a rich, interactive terminal menu that automatically adapts to your current session state:

- **No Credentials**: Prompts for your `api_id` and `api_hash`, which are actively validated and securely saved in your local configuration directory (e.g., `~/.config/chronochat/config.env`).
- **Not Logged In**: Prompts you to log in. Enter your phone number, the login code sent to your Telegram, and your Two-Step Verification password if enabled.
- **Logged In**: 
  - **Show Chat List**: Fetch and browse all your chats dynamically. Chats are paginated (10 per page) for easy viewing. You can use the **Search** feature to quickly filter chats by their name.
  - **Log Out**: Securely disconnect and destroy your local session.

This interactive menu uses `questionary` for smooth arrow-key navigation and intuitive prompts. Future runs will load your authenticated configuration automatically without any login prompts.

## Roadmap

- ✅ Proof of concept using Telethon (in progress, cannot create Telegram app yet)
- 📥 Download media from chats (add date/chat filter controls)
- 🛠️ Add EXIF tool to modify media metadata
- 🌐 Support other messengers

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.


