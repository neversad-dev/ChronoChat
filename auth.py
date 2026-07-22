from telethon import TelegramClient
from telethon.errors import ApiIdInvalidError
from telethon.sessions import StringSession
import config

async def validate_credentials(api_id, api_hash):
    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.connect()
        from telethon.errors import AccessTokenInvalidError
        try:
            # We attempt a dummy bot login. 
            # If API credentials are bad, it throws ApiIdInvalidError.
            # If they are good, it throws AccessTokenInvalidError because the bot token is fake.
            await client.sign_in(bot_token='12345:invalid')
        except AccessTokenInvalidError:
            return True, "Valid credentials"
            
        return True, "Valid credentials"
    except ApiIdInvalidError:
        return False, "Invalid API ID or Hash."
    except Exception as e:
        return False, f"Connection error: {e}"
    finally:
        await client.disconnect()

async def get_client(api_id, api_hash):
    session_path = config.get_session_path()
    client = TelegramClient(str(session_path), api_id, api_hash)
    try:
        await client.connect()
        return client
    except Exception:
        await client.disconnect()
        raise

async def is_authorized(client):
    return await client.is_user_authorized()
