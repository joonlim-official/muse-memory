"""Two-way sync between muse-memory markdown files and Notion.

Public, optional component of the personal-memory-system skill. Stdlib
Python only — no third-party dependencies.

Layout:
    config.py    environment-based configuration
    markdown.py  Markdown <-> Notion block conversion (loss-aware)
    transport.py Notion API transport (urllib) + in-memory fake for tests
    engine.py    three-way reconciliation, push, snapshot, restore
    cli.py       command-line interface (also runnable as __main__)
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
