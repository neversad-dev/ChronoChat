import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv, set_key
from telethon import TelegramClient

APP_NAME = "chronochat"

def get_config_dir():
    """Return the path to the user's config directory (XDG Base Directory compliant)."""
    # Use XDG_CONFIG_HOME if set, otherwise ~/.config
    xdg_config = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config_dir = Path(xdg_config) / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def ensure_credentials(env_path):
    """Ensure TG_API_ID and TG_API_HASH are set in the env_path."""
    load_dotenv(env_path)
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")

    if not api_id or not api_hash:
        print("[!] Welcome to ChronoChat!")
        print("[!] To proceed, you need your Telegram API credentials.")
        print("[!] Get them by logging into https://my.telegram.org/ and creating an application.\n")
        
        while True:
            api_id = input("Enter your App api_id (integer): ").strip()
            if api_id.isdigit():
                break
            print("[-] Error: api_id must be a number.")
            
        api_hash = input("Enter your App api_hash (string): ").strip()
        
        # Save them to the env file
        env_path.touch(exist_ok=True)
        set_key(str(env_path), "TG_API_ID", api_id)
        set_key(str(env_path), "TG_API_HASH", api_hash)
        print(f"\n[+] 1. **API Credentials**: It will prompt you for the `api_id` and `api_hash` you generated earlier. These are securely saved in your local configuration directory (e.g., `~/.config/chronochat/config.env`).")

    return int(api_id), api_hash

async def main():
    config_dir = get_config_dir()
    env_path = config_dir / "config.env"
    session_path = config_dir / "chronochat" # Telethon adds .session

    api_id, api_hash = ensure_credentials(env_path)

    print(f"[+] Using config directory: {config_dir}")
    print("[+] Initializing Telegram Client...")
    
    # Initialize client using the session path in the config directory
    client = TelegramClient(str(session_path), api_id, api_hash)

    # client.start() automatically prompts for phone number and authorization code
    # on the console if not already authorized.
    # This authenticates your device and creates a local `chronochat.session` file in your config directory. Future runs will load this configuration automatically without any prompts.
    await client.start()

    print("[+] Connected successfully!")
    
    # Retrieve details about the authorized user
    me = await client.get_me()
    username = f"@{me.username}" if me.username else "No username"
    print(f"[+] Logged in as: {me.first_name} {me.last_name or ''} ({username})")

    # Send a proof-of-concept message to your own "Saved Messages" channel ("me")
    print("[+] Sending a test message to your Saved Messages...")
    await client.send_message("me", "Hello from Telethon on Nix!")
    print("[+] Message sent successfully!")

    # Disconnect the client
    await client.disconnect()
    print("[+] Done.")

if __name__ == "__main__":
    # Run the async main function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[-] Operation cancelled by user.")
        sys.exit(0)
