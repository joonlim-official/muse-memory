"""Environment-based configuration for notion-sync.

Every setting comes from the environment — no installation-specific
values are ever hard-coded. All public code, tests, and docs must stay
free of user-specific names, paths, page IDs, and credentials.
"""

import os
from dataclasses import dataclass, field


def _default_guard_bin() -> str:
    # <skill>/lib/notion_sync/config.py -> <skill>/bin/memory-guard
    here = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(os.path.dirname(here))
    return os.path.join(skill_dir, "bin", "memory-guard")


@dataclass
class Config:
    """Resolved runtime configuration."""

    memory_root: str          # root of the memory installation
    api_key: str              # Notion internal-integration token
    hub_id: str               # parent page ID hosting the live tree
    state_dir: str            # sync state (page map, snapshots, conflicts)
    guard_bin: str            # memory-guard executable for incoming scans
    tz: str                   # IANA timezone for dated snapshot titles
    api_base: str             # Notion API base URL
    api_version: str          # Notion-Version header value
    exclude: tuple = field(default_factory=tuple)  # glob patterns, rel to root

    @property
    def pages_file(self) -> str:
        return os.path.join(self.state_dir, "pages.json")

    @property
    def conflicts_file(self) -> str:
        return os.path.join(self.state_dir, "conflicts.json")

    @property
    def snapshots_file(self) -> str:
        return os.path.join(self.state_dir, "snapshots.json")

    @property
    def deletions_file(self) -> str:
        return os.path.join(self.state_dir, "deletions.json")

    @property
    def last_run_file(self) -> str:
        return os.path.join(self.state_dir, "last_run.json")

    @property
    def base_dir(self) -> str:
        """Directory holding last-synced per-file snapshots (3-way base)."""
        return os.path.join(self.state_dir, "base")


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


def load_config(env=None) -> Config:
    """Build a Config from the environment. Raises ConfigError on gaps."""
    env = os.environ if env is None else env

    memory_root = (
        env.get("NOTION_SYNC_MEMORY_ROOT")
        or env.get("PERSONAL_MEMORY_ROOT")
        or ""
    ).strip()
    if not memory_root:
        raise ConfigError(
            "memory root is not set: export NOTION_SYNC_MEMORY_ROOT "
            "(or PERSONAL_MEMORY_ROOT) to the memory installation root"
        )
    memory_root = os.path.abspath(os.path.expanduser(memory_root))

    api_key = (env.get("NOTION_API_KEY") or "").strip()
    if not api_key:
        raise ConfigError(
            "NOTION_API_KEY is not set: create a Notion internal integration "
            "and export its token (see references/notion-sync.md)"
        )

    hub_id = (env.get("NOTION_HUB_ID") or "").strip()
    if not hub_id:
        raise ConfigError(
            "NOTION_HUB_ID is not set: export the ID of the Notion page "
            "that hosts the live memory tree"
        )

    state_dir = (env.get("NOTION_STATE_DIR") or "").strip()
    if not state_dir:
        state_dir = os.path.join(memory_root, ".notion-sync")
    state_dir = os.path.abspath(os.path.expanduser(state_dir))

    guard_bin = (env.get("NOTION_GUARD_BIN") or "").strip() or _default_guard_bin()
    tz = (env.get("NOTION_TZ") or "America/Los_Angeles").strip()
    api_base = (env.get("NOTION_API_BASE") or "https://api.notion.com").strip().rstrip("/")
    api_version = (env.get("NOTION_API_VERSION") or "2022-06-28").strip()

    exclude_raw = (env.get("NOTION_SYNC_EXCLUDE") or "").strip()
    exclude = tuple(p.strip() for p in exclude_raw.split(",") if p.strip())

    return Config(
        memory_root=memory_root,
        api_key=api_key,
        hub_id=hub_id,
        state_dir=state_dir,
        guard_bin=guard_bin,
        tz=tz,
        api_base=api_base,
        api_version=api_version,
        exclude=exclude,
    )
