import asyncio
import sys
from cli import main_loop

def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("\n[-] Operation cancelled by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()
