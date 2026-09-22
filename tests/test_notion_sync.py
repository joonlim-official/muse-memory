"""Synthetic tests for notion-sync. No credentials, no network.

Everything runs against FakeNotionTransport and temporary directories.
All fixture content is synthetic and impersonal.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from notion_sync import markdown as md
from notion_sync import transport as tp
from notion_sync.config import Config, load_config, ConfigError
from notion_sync.engine import Engine, validate_adoption_relpath


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_cfg(tmp_path, **over):
    kw = dict(
        memory_root=str(tmp_path / "mem"),
        api_key="test-key",
        hub_id="hub-1",
        state_dir=str(tmp_path / "state"),
        guard_bin="/nonexistent/guard",
        tz="America/Los_Angeles",
        api_base="https://api.notion.com",
        api_version="2022-06-28",
        exclude=(),
    )
    kw.update(over)
    os.makedirs(kw["memory_root"], exist_ok=True)
    return Config(**kw)


def make_engine(tmp_path, guard=None, **over):
    cfg = make_cfg(tmp_path, **over)
    transport = tp.FakeNotionTransport()
    # hub page must exist for create_page under it
    transport.pages["hub-1"] = {"title": "Hub", "archived": False,
                                "blocks": []}
    engine = Engine(cfg, transport,
                    guard_check=(guard or (lambda text: 0)))
    return engine, transport, cfg


def write_mem(cfg, rel, text):
    abs_p = os.path.join(cfg.memory_root, rel)
    os.makedirs(os.path.dirname(abs_p), exist_ok=True)
    with open(abs_p, "w", encoding="utf-8") as f:
        f.write(text)
    return abs_p


def read_mem(cfg, rel):
    with open(os.path.join(cfg.memory_root, rel), encoding="utf-8") as f:
        return f.read()


SAMPLE = """---
title: Sample
---

# Heading one

A paragraph with **bold**, *italic*, `code`, and a [link](https://example.com).

- bullet one
  - nested bullet
- [ ] todo open
- [x] todo done

1. first
2. second

> a quote

```
code block
  indented line
```

| a | b |
|---|---|
| 1 | 2 |

---

Unicode: héllo wörld 🎉 — em dash.
"""


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def test_load_config_requires_memory_root():
    with pytest.raises(ConfigError):
        load_config(env={})


def test_load_config_requires_api_key_and_hub(tmp_path):
    env = {"NOTION_SYNC_MEMORY_ROOT": str(tmp_path)}
    with pytest.raises(ConfigError):
        load_config(env=env)
    env["NOTION_API_KEY"] = "k"
    with pytest.raises(ConfigError):
        load_config(env=env)
    env["NOTION_HUB_ID"] = "h"
    cfg = load_config(env=env)
    assert cfg.memory_root == str(tmp_path)
    assert cfg.state_dir == os.path.join(str(tmp_path), ".notion-sync")


# ---------------------------------------------------------------------------
# markdown round-trips
# ---------------------------------------------------------------------------

def test_frontmatter_round_trip():
    text = "---\ntitle: Sample\ntags: [a, b]\n---\n\nBody text.\n"
    blocks = md.parse_markdown(text)
    assert blocks[0]["type"] == "frontmatter"
    out = md.blocks_to_markdown(blocks)
    assert out == text, f"frontmatter changed:\n{out!r}\nvs\n{text!r}"


def test_full_sample_round_trip():
    blocks = md.parse_markdown(SAMPLE)
    out = md.blocks_to_markdown(blocks)
    assert md.canonical_text(out) == md.canonical_text(SAMPLE)


def test_notion_block_round_trip():
    blocks = md.parse_markdown(SAMPLE)
    api = tp.blocks_to_notion(blocks)
    back = tp.notion_to_blocks(api)
    assert md.canonical(blocks) == md.canonical(back)


def test_multiple_tables_round_trip():
    text = ("| a | b |\n|---|---|\n| 1 | 2 |\n\n"
            "Between.\n\n"
            "| x | y | z |\n|---|---|---|\n| 7 | 8 | 9 |\n")
    blocks = md.parse_markdown(text)
    tables = [b for b in blocks if b["type"] == "table"]
    assert len(tables) == 2
    assert tables[0]["rows"][0][0][0]["text"] == "a"
    assert tables[1]["rows"][1][2][0]["text"] == "9"
    api = tp.blocks_to_notion(blocks)
    back = tp.notion_to_blocks(api)
    assert md.canonical(blocks) == md.canonical(back)


def test_nested_list_structure_preserved():
    text = "- a\n  - b\n    - c\n- d\n"
    blocks = md.parse_markdown(text)
    out = md.blocks_to_markdown(blocks)
    assert out == text


def test_code_block_indentation_preserved():
    text = "```python\ndef f():\n    return 1\n```\n"
    blocks = md.parse_markdown(text)
    assert blocks[0]["type"] == "code"
    assert blocks[0]["language"] == "python"
    out = md.blocks_to_markdown(blocks)
    assert out == text


def test_meaningful_blank_lines_preserved():
    # Notion has no multi-blank concept; what matters is that paragraphs
    # stay separated (not joined) through the round-trip.
    text = "Para one.\n\n\nPara two after two blanks.\n"
    blocks = md.parse_markdown(text)
    out = md.blocks_to_markdown(blocks)
    assert "Para one." in out and "Para two after two blanks." in out
    assert "\n\n" in out  # still separated by a blank line


def test_headings_all_levels():
    text = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6\n"
    blocks = md.parse_markdown(text)
    types = [b["type"] for b in blocks]
    # Notion only has 3 heading levels; H4-H6 degrade to heading_3
    assert types == ["heading_1", "heading_2", "heading_3",
                     "heading_3", "heading_3", "heading_3"]
    out = md.blocks_to_markdown(blocks)
    assert md.canonical_text(out) == md.canonical_text(
        "# H1\n## H2\n### H3\n### H4\n### H5\n### H6\n")


def test_unicode_and_links():
    text = "héllo [wörld](https://example.com/ü) 🎉\n"
    blocks = md.parse_markdown(text)
    api = tp.blocks_to_notion(blocks)
    back = tp.notion_to_blocks(api)
    assert md.canonical(blocks) == md.canonical(back)


# ---------------------------------------------------------------------------
# engine: init + basic sync
# ---------------------------------------------------------------------------

def test_init_creates_pages_and_base(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/people/jane-doe.md", "# Jane Doe\n")
    code, report = engine.init()
    assert code == 0
    assert set(report["created"]) == {"MEMORY.md", "memory/people/jane-doe.md"}
    assert set(engine.state.pages) == {"MEMORY.md", "memory/people/jane-doe.md"}
    # base snapshots exist
    assert engine.state.read_base("MEMORY.md") == "# Memory\n"
    # second init is a no-op mapping-wise
    code2, report2 = engine.init()
    assert code2 == 0
    assert set(report2["mapped"]) == {"MEMORY.md", "memory/people/jane-doe.md"}


def test_sync_clean_noop(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    code, report = engine.sync()
    assert code == 0
    assert report["plan"]["clean"] == 1
    assert report["plan"]["push"] == 0


def test_local_only_edit_pushes(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    write_mem(cfg, "MEMORY.md", "# Memory\n\nNew line.\n")
    code, report = engine.sync()
    assert code == 0
    assert report["plan"]["push"] == 1
    assert report["pushed"] == ["MEMORY.md"]
    # remote now matches local
    page_id = engine.state.pages["MEMORY.md"]
    blocks = tp.notion_to_blocks(transport.get_blocks(page_id))
    assert md.blocks_to_markdown(blocks) == "# Memory\n\nNew line.\n"


def test_notion_only_edit_pulls(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    page_id = engine.state.pages["MEMORY.md"]
    transport.replace_blocks(page_id, md.parse_markdown("# Memory\n\nFrom Notion.\n"))
    code, report = engine.sync()
    assert code == 0
    assert report["pulled"] == ["MEMORY.md"]
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n\nFrom Notion.\n"


def test_simultaneous_conflict(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    write_mem(cfg, "MEMORY.md", "# Memory\n\nLocal edit.\n")
    page_id = engine.state.pages["MEMORY.md"]
    transport.replace_blocks(page_id, md.parse_markdown("# Memory\n\nNotion edit.\n"))
    code, report = engine.sync()
    assert code == 1
    assert report["conflicts"] == ["MEMORY.md"]
    # neither side overwritten
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n\nLocal edit.\n"
    blocks = tp.notion_to_blocks(transport.get_blocks(page_id))
    assert md.blocks_to_markdown(blocks) == "# Memory\n\nNotion edit.\n"
    # no snapshot taken on conflict
    assert engine.state.snapshots == {}


def test_notion_deletion_reported_not_deleted(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    page_id = engine.state.pages["MEMORY.md"]
    transport.archive_page(page_id)
    code, report = engine.sync()
    assert code == 1
    assert report["deletions"] == ["MEMORY.md"]
    assert os.path.exists(os.path.join(cfg.memory_root, "MEMORY.md"))
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n"


def test_new_local_file_creates_page(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    write_mem(cfg, "memory/topics/synthetic-topic.md", "# Synthetic\n")
    code, report = engine.sync()
    assert code == 0
    assert report["created"] == ["memory/topics/synthetic-topic.md"]
    page_id = engine.state.pages["memory/topics/synthetic-topic.md"]
    blocks = tp.notion_to_blocks(transport.get_blocks(page_id))
    assert md.blocks_to_markdown(blocks) == "# Synthetic\n"


def test_adopt_new_notion_page(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    pid = transport.create_page("hub-1", "memory/topics/from-notion.md")
    transport.replace_blocks(pid, md.parse_markdown("# From Notion\n"))
    code, report = engine.sync()
    assert code == 0
    assert report["adopted"] == ["memory/topics/from-notion.md"]
    assert read_mem(cfg, "memory/topics/from-notion.md") == "# From Notion\n"


def test_adopt_path_traversal_rejected(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    pid = transport.create_page("hub-1", "../evil.md")
    transport.replace_blocks(pid, md.parse_markdown("evil\n"))
    code, report = engine.sync()
    assert code == 1
    assert report["errors"]
    assert not os.path.exists(os.path.join(cfg.memory_root, "evil.md"))


def test_adopt_collision_rejected(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/topics/existing.md", "# Existing\n")
    engine.init()
    pid = transport.create_page("hub-1", "memory/topics/existing.md")
    transport.replace_blocks(pid, md.parse_markdown("# Other\n"))
    code, report = engine.sync()
    assert code == 1
    assert report["errors"]


# ---------------------------------------------------------------------------
# guard behavior
# ---------------------------------------------------------------------------

def test_incoming_secret_blocked(tmp_path):
    engine, transport, cfg = make_engine(
        tmp_path, guard=lambda text: 1 if "SECRET" in text else 0)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    page_id = engine.state.pages["MEMORY.md"]
    transport.replace_blocks(page_id, md.parse_markdown("ssn SECRET 123\n"))
    code, report = engine.sync()
    assert code == 1
    assert report["blocks"]
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n"


def test_incoming_review_hold(tmp_path):
    engine, transport, cfg = make_engine(
        tmp_path, guard=lambda text: 2 if "REVIEWME" in text else 0)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    page_id = engine.state.pages["MEMORY.md"]
    transport.replace_blocks(page_id, md.parse_markdown("REVIEWME figure\n"))
    code, report = engine.sync()
    assert code == 1
    assert report["holds"]
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n"


def test_outgoing_secret_blocked(tmp_path):
    engine, transport, cfg = make_engine(
        tmp_path, guard=lambda text: 1 if "SECRET" in text else 0)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    write_mem(cfg, "MEMORY.md", "# Memory\nSECRET data\n")
    code, report = engine.sync()
    assert code == 1
    assert report["blocks"]
    page_id = engine.state.pages["MEMORY.md"]
    blocks = tp.notion_to_blocks(transport.get_blocks(page_id))
    assert md.blocks_to_markdown(blocks) == "# Memory\n"


# ---------------------------------------------------------------------------
# failure atomicity
# ---------------------------------------------------------------------------

def test_failed_pull_prevents_push_and_snapshot(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    write_mem(cfg, "MEMORY.md", "# Memory\nLocal change.\n")
    transport.fail_on = "get_blocks"
    with pytest.raises(Exception):
        engine.sync()
    transport.fail_on = None
    # nothing advanced: no snapshot, base unchanged
    assert engine.state.snapshots == {}
    assert engine.state.read_base("MEMORY.md") == "# Memory\n"


def test_failed_push_prevents_snapshot(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    write_mem(cfg, "MEMORY.md", "# Memory\nLocal change.\n")
    transport.fail_on = "replace_blocks"
    with pytest.raises(Exception):
        engine.sync()
    transport.fail_on = None
    assert engine.state.snapshots == {}


# ---------------------------------------------------------------------------
# snapshot + restore
# ---------------------------------------------------------------------------

def test_snapshot_and_staged_restore(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/people/jane-doe.md", "# Jane Doe\n")
    engine.init()
    code, report = engine.sync()
    assert code == 0
    snap_id = report["snapshot_page_id"]
    assert snap_id
    # corrupt the live file, then restore to staging
    write_mem(cfg, "MEMORY.md", "CORRUPTED\n")
    staging = str(tmp_path / "staging")
    rpt = engine.restore(snap_id, staging)
    assert rpt["total"] == 2
    with open(os.path.join(staging, "MEMORY.md")) as f:
        assert f.read() == "# Memory\n"
    # live file untouched by restore
    assert read_mem(cfg, "MEMORY.md") == "CORRUPTED\n"
    # accounting: one mismatch (MEMORY.md), one byte-identical
    assert rpt["byte_identical"] == 1
    assert len(rpt["mismatches"]) == 1


def test_validate_adoption_relpath():
    ok, err = validate_adoption_relpath("memory/people/jane.md", "/mem")
    assert ok == "memory/people/jane.md" and err is None
    ok, err = validate_adoption_relpath("../evil.md", "/mem")
    assert ok is None and err
    ok, err = validate_adoption_relpath("/abs/path.md", "/mem")
    assert ok is None and err
    ok, err = validate_adoption_relpath("not-markdown.txt", "/mem")
    assert ok is None and err
    ok, err = validate_adoption_relpath("memory/bogus/x.md", "/mem")
    assert ok is None and err
