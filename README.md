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

A Python application for interacting with the Telegram API using Telethon, managed via a multiplatform Nix dev shell. ChronoChat downloads media from your chats and attaches proper timestamps.

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

### 3. Interactive Configuration (First Run Only)

On your first run, the script will guide you through setting up your configuration:
1. **API Credentials**: It will prompt you for the `api_id` and `api_hash` you generated earlier. These are securely saved in your local configuration directory (e.g., `~/.config/chronochat/config.env`).
2. **Log In to Telegram**: Telethon will then prompt you to log in:
   - **Phone number**: Enter your full phone number including the country code (e.g. `+12345678900`).
   - **Code**: Enter the login code Telegram sends to your other active sessions (or SMS).
   - **Password**: If you have Two-Factor Authentication (2FA) enabled, enter your password.

This authenticates your device and creates a local `chronochat.session` file in your config directory. Future runs will load this configuration automatically without any prompts.

## Roadmap

- ✅ Proof of concept using Telethon (in progress, cannot create Telegram app yet)
- 📥 Download media from chats (add date/chat filter controls)
- 🛠️ Add EXIF tool to modify media metadata
- 🌐 Support other messengers

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.


