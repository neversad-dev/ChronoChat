import os
from pathlib import Path
from dotenv import load_dotenv, set_key

APP_NAME = "chronochat"

def get_config_dir():
    xdg_config = os.getenv("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config_dir = Path(xdg_config) / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_env_path():
    return get_config_dir() / "config.env"

def get_session_path():
    return get_config_dir() / "chronochat"

def get_credentials():
    env_path = get_env_path()
    # We load directly from the file to avoid stale os.environ values if the file is deleted
    from dotenv import dotenv_values
    env_dict = dotenv_values(env_path)
    
    # Fallback to os.getenv in case they are provided via actual env vars (e.g. direnv)
    api_id = env_dict.get("TG_API_ID") or os.getenv("TG_API_ID")
    api_hash = env_dict.get("TG_API_HASH") or os.getenv("TG_API_HASH")
    
    if api_id and api_hash:
        try:
            return int(api_id), api_hash
        except ValueError:
            return None, None
    return None, None

def save_credentials(api_id: int, api_hash: str):
    env_path = get_env_path()
    env_path.touch(exist_ok=True)
    set_key(str(env_path), "TG_API_ID", str(api_id))
    set_key(str(env_path), "TG_API_HASH", api_hash)
    
    # Update os.environ so current process knows
    os.environ["TG_API_ID"] = str(api_id)
    os.environ["TG_API_HASH"] = api_hash

def get_download_dir():
    env_path = get_env_path()
    from dotenv import dotenv_values
    env_dict = dotenv_values(env_path)
    
    download_dir = env_dict.get("DOWNLOAD_DIR") or os.getenv("DOWNLOAD_DIR")
    if download_dir:
        return download_dir
    return os.path.expanduser("~/Downloads/chronochat")

def set_download_dir(path: str):
    env_path = get_env_path()
    env_path.touch(exist_ok=True)
    set_key(str(env_path), "DOWNLOAD_DIR", path)
    os.environ["DOWNLOAD_DIR"] = path

def clear_credentials():
    env_path = get_env_path()
    if env_path.exists():
        env_path.unlink()
        
    # Remove from os.environ so they aren't cached for the rest of the application lifetime
    os.environ.pop("TG_API_ID", None)
    os.environ.pop("TG_API_HASH", None)
    
    session_file = get_session_path().with_suffix(".session")
    if session_file.exists():
        session_file.unlink()
