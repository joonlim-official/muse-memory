"""Run notion-sync as a module: python3 -m notion_sync <command> ..."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
