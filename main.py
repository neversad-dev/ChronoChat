import asyncio
import sys
from cli import main_loop

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n[-] Operation cancelled by user.")
        sys.exit(0)
