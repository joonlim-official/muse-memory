"""Synthetic tests for notion-sync. No credentials, no network.

Everything runs against FakeNotionTransport and temporary directories.
All fixture content is synthetic and impersonal.
"""

import json
import os
import subprocess
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
    # hardened policy cases
    ok, err = validate_adoption_relpath("memory/bank/secret.md", "/mem")
    assert ok is None and "runtime-managed" in err
    ok, err = validate_adoption_relpath("memory/2026-09-22.md", "/mem")
    assert ok is None and "daily logs" in err
    ok, err = validate_adoption_relpath("memory/people/INDEX.md", "/mem")
    assert ok is None and "reserved" in err
    ok, err = validate_adoption_relpath("memory/.hidden/x.md", "/mem")
    assert ok is None and "hidden" in err
    ok, err = validate_adoption_relpath(
        "memory/people/Jane-Doe.md", "/mem",
        existing_rels={"memory/people/jane-doe.md"})
    assert ok is None and "collides" in err


# ---------------------------------------------------------------------------
# rollback: failed apply leaves nothing half-written
# ---------------------------------------------------------------------------

def test_apply_rolls_back_partial_pulls(tmp_path, monkeypatch):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/people/jane-doe.md", "# Jane\n")
    engine.init()
    for rel, new in (("MEMORY.md", "# Memory\n\nR1.\n"),
                     ("memory/people/jane-doe.md", "# Jane\n\nR2.\n")):
        transport.replace_blocks(engine.state.pages[rel],
                                 md.parse_markdown(new))
    plan, local_files, remote = engine.plan()
    assert plan.actionable() and len(plan.pull) == 2
    calls = {"n": 0}
    orig_write = engine._write_local

    def flaky(abs_p, text):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("injected write failure")
        return orig_write(abs_p, text)

    monkeypatch.setattr(engine, "_write_local", flaky)
    with pytest.raises(OSError):
        engine.apply(plan, local_files, remote)
    # the first pull was rolled back: both files keep pre-apply content
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n"
    assert read_mem(cfg, "memory/people/jane-doe.md") == "# Jane\n"
    assert engine.state.snapshots == {}
    assert engine.state.read_base("MEMORY.md") == "# Memory\n"


def test_apply_rolls_back_partial_pushes(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "EXTRA.md", "# Extra\n")
    engine.init()
    write_mem(cfg, "MEMORY.md", "# Memory\n\nL1.\n")
    write_mem(cfg, "EXTRA.md", "# Extra\n\nL2.\n")
    plan, local_files, remote = engine.plan()
    assert plan.actionable() and len(plan.push) == 2
    transport.calls.clear()
    transport.fail_on = ("replace_blocks", 2)  # fail on the 2nd push only
    with pytest.raises(tp.TransportError):
        engine.apply(plan, local_files, remote)
    transport.fail_on = None
    # the first push was rolled back: remote still has the old content
    pid = engine.state.pages["MEMORY.md"]
    blocks = tp.notion_to_blocks(transport.get_blocks(pid))
    assert md.blocks_to_markdown(blocks) == "# Memory\n"
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n\nL1.\n"
    assert engine.state.snapshots == {}


def test_apply_rolls_back_adopt_and_snapshot(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/people/INDEX.md",
              "# People\n\n- **Jane** — `memory/people/jane.md` — x\n")
    engine.init()
    pid = transport.create_page("hub-1", "memory/people/john.md")
    transport.replace_blocks(pid, md.parse_markdown("# John\n"))
    transport.calls.clear()
    transport.fail_on = ("create_page", 1)  # snapshot creation fails
    from notion_sync.engine import SyncError
    with pytest.raises(SyncError, match="apply failed"):
        engine.sync()
    transport.fail_on = None
    # adopted file removed, INDEX.md restored, mapping dropped, no snapshot
    assert not os.path.exists(os.path.join(cfg.memory_root,
                                            "memory/people/john.md"))
    assert read_mem(cfg, "memory/people/INDEX.md") == \
        "# People\n\n- **Jane** — `memory/people/jane.md` — x\n"
    assert "memory/people/john.md" not in engine.state.pages
    assert engine.state.snapshots == {}


# ---------------------------------------------------------------------------
# adoption: INDEX.md updates + hardened routing
# ---------------------------------------------------------------------------

def test_adopt_updates_index_md(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/people/INDEX.md",
              "# People\n\n- **Jane Doe** — `memory/people/jane-doe.md` — test\n")
    write_mem(cfg, "memory/people/jane-doe.md", "# Jane Doe\n")
    engine.init()
    pid = transport.create_page("hub-1", "memory/people/john-smith.md")
    transport.replace_blocks(pid, md.parse_markdown("# John Smith\n"))
    code, report = engine.sync()
    assert code == 0
    assert report["adopted"] == ["memory/people/john-smith.md"]
    assert report["index_updated"] == ["memory/people/john-smith.md"]
    idx = read_mem(cfg, "memory/people/INDEX.md")
    assert idx.count("`memory/people/john-smith.md`") == 1  # one entry


def test_adopt_without_index_is_reported(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    pid = transport.create_page("hub-1", "memory/topics/lonely.md")
    transport.replace_blocks(pid, md.parse_markdown("# Lonely\n"))
    code, report = engine.sync()
    assert code == 0
    assert report["adopted"] == ["memory/topics/lonely.md"]
    assert report["index_missing"] == ["memory/topics/lonely.md"]


def test_adopt_bank_rejected(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    pid = transport.create_page("hub-1", "memory/bank/sneaky.md")
    transport.replace_blocks(pid, md.parse_markdown("sneaky\n"))
    code, report = engine.sync()
    assert code == 1
    assert any("runtime-managed" in e[1] for e in report["errors"])
    assert not os.path.exists(
        os.path.join(cfg.memory_root, "memory/bank/sneaky.md"))


def test_adopt_case_collision_rejected(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/people/jane-doe.md", "# Jane\n")
    engine.init()
    pid = transport.create_page("hub-1", "memory/people/JANE-DOE.md")
    transport.replace_blocks(pid, md.parse_markdown("# Other Jane\n"))
    code, report = engine.sync()
    assert code == 1
    assert any("collides" in e[1] for e in report["errors"])


# ---------------------------------------------------------------------------
# init: existing pages are compared, never silently clobbered
# ---------------------------------------------------------------------------

def test_init_existing_empty_page_seeds(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    transport.create_page("hub-1", "MEMORY.md")  # empty page, no blocks
    code, report = engine.init()
    assert code == 0
    assert report["seeded_existing"] == ["MEMORY.md"]
    pid = engine.state.pages["MEMORY.md"]
    blocks = tp.notion_to_blocks(transport.get_blocks(pid))
    assert md.blocks_to_markdown(blocks) == "# Memory\n"


def test_init_existing_equal_page_adopts_without_rewrite(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    pid = transport.create_page("hub-1", "MEMORY.md")
    transport.replace_blocks(pid, md.parse_markdown("# Memory\n"))
    replaced_before = transport.replaced
    code, report = engine.init()
    assert code == 0
    assert report["adopted_existing"] == ["MEMORY.md"]
    assert transport.replaced == replaced_before  # nothing rewritten


def test_init_existing_differing_page_is_mismatch(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    pid = transport.create_page("hub-1", "MEMORY.md")
    transport.replace_blocks(pid, md.parse_markdown("# Other\n"))
    code, report = engine.init()
    assert code == 1
    assert report["content_mismatch"] == ["MEMORY.md"]
    assert "MEMORY.md" not in engine.state.pages
    # neither side clobbered
    assert read_mem(cfg, "MEMORY.md") == "# Memory\n"
    blocks = tp.notion_to_blocks(transport.get_blocks(pid))
    assert md.blocks_to_markdown(blocks) == "# Other\n"


# ---------------------------------------------------------------------------
# replace_blocks: canonical no-op
# ---------------------------------------------------------------------------

def test_replace_blocks_noop_when_canonically_identical(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    engine.init()
    pid = engine.state.pages["MEMORY.md"]
    replaced_before = transport.replaced
    # canonically identical (trailing blank-line style differs only)
    transport.replace_blocks(pid, md.parse_markdown("# Memory\n\n\n"))
    assert transport.replaced == replaced_before
    # genuinely different content still replaces
    transport.replace_blocks(pid, md.parse_markdown("# Changed\n"))
    assert transport.replaced == replaced_before + 1


# ---------------------------------------------------------------------------
# restore: exact per-category accounting
# ---------------------------------------------------------------------------

def test_restore_accounting_exact(tmp_path):
    engine, transport, cfg = make_engine(tmp_path)
    write_mem(cfg, "MEMORY.md", "# Memory\n")
    write_mem(cfg, "memory/people/jane-doe.md", "# Jane Doe\n")
    # double blank line: Notion round-trip normalizes it away
    write_mem(cfg, "memory/people/john-smith.md", "# John Smith\n\n\nBody.\n")
    write_mem(cfg, "memory/people/temp.md", "# Temp\n")
    engine.init()
    code, report = engine.sync()
    assert code == 0
    snap_id = report["snapshot_page_id"]
    # mismatch: genuinely different content
    write_mem(cfg, "MEMORY.md", "CORRUPTED\n")
    # snapshot_only: delete the live file after the snapshot
    os.remove(os.path.join(cfg.memory_root, "memory/people/temp.md"))
    # live_only: new file created after the snapshot
    write_mem(cfg, "memory/people/brand-new.md", "# Brand New\n")
    staging = str(tmp_path / "staging")
    rpt = engine.restore(snap_id, staging)
    assert rpt["total"] == 4
    assert rpt["byte_identical"] == 1          # jane-doe.md
    assert rpt["equivalent"] == 1              # john-smith.md (blanks)
    assert rpt["mismatches"] == [("MEMORY.md", "content differs")]
    assert rpt["snapshot_only"] == ["memory/people/temp.md"]
    assert rpt["live_only"] == ["memory/people/brand-new.md"]
    with open(os.path.join(staging, "memory/people/jane-doe.md")) as f:
        assert f.read() == "# Jane Doe\n"


# ---------------------------------------------------------------------------
# CLI end to end through bin/memory-notion-sync (fake transport on disk)
# ---------------------------------------------------------------------------

def _cli_env(tmp_path):
    mem = tmp_path / "climem"
    mem.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update({
        "NOTION_SYNC_MEMORY_ROOT": str(mem),
        "NOTION_API_KEY": "test-key",
        "NOTION_HUB_ID": "hub-1",
        "NOTION_STATE_DIR": str(tmp_path / "clistate"),
        "NOTION_SYNC_FAKE_TRANSPORT": "1",
        "NOTION_SYNC_FAKE_FILE": str(tmp_path / "fake.json"),
    })
    return env, mem


def _run_cli(env, *argv):
    bin_path = os.path.join(os.path.dirname(__file__), "..", "bin",
                            "memory-notion-sync")
    return subprocess.run([bin_path, "--no-guard", *argv],
                          capture_output=True, text=True, env=env,
                          timeout=120)


def _remote_edit_fake(env, rel, new_text):
    """Edit a page's blocks directly in the persisted fake transport."""
    fake_path = env["NOTION_SYNC_FAKE_FILE"]
    with open(fake_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pid = next((_id for _id, p in data["pages"].items()
                if p["title"] == rel and not p["archived"]), None)
    assert pid, f"no live page titled {rel}"
    data["pages"][pid]["blocks"] = tp.blocks_to_notion(
        md.parse_markdown(new_text))
    tmp = fake_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, fake_path)


def test_cli_init_sync_status(tmp_path):
    env, mem = _cli_env(tmp_path)
    (mem / "MEMORY.md").write_text("# Memory\n")
    p = _run_cli(env, "init")
    assert p.returncode == 0, p.stderr
    p = _run_cli(env, "status")
    assert p.returncode == 0, p.stderr
    assert "clean=1" in p.stdout
    p = _run_cli(env, "sync", "--json")
    assert p.returncode == 0, p.stderr
    body = json.loads(p.stdout)
    assert body["plan"]["clean"] == 1


def test_cli_conflict_exit_1(tmp_path):
    env, mem = _cli_env(tmp_path)
    (mem / "MEMORY.md").write_text("# Memory\n")
    assert _run_cli(env, "init").returncode == 0
    assert _run_cli(env, "sync").returncode == 0
    (mem / "MEMORY.md").write_text("# Memory\n\nLocal edit.\n")
    _remote_edit_fake(env, "MEMORY.md", "# Memory\n\nNotion edit.\n")
    p = _run_cli(env, "sync")
    assert p.returncode == 1, p.stderr + p.stdout
    assert "conflicts" in p.stdout
    # neither side overwritten
    assert (mem / "MEMORY.md").read_text() == "# Memory\n\nLocal edit.\n"


def test_cli_config_error_exit_2(tmp_path):
    env, _mem = _cli_env(tmp_path)
    del env["NOTION_API_KEY"]
    p = _run_cli(env, "status")
    assert p.returncode == 2
    assert "configuration error" in p.stderr


def test_cli_restore_end_to_end(tmp_path):
    env, mem = _cli_env(tmp_path)
    (mem / "MEMORY.md").write_text("# Memory\n")
    assert _run_cli(env, "init").returncode == 0
    p = _run_cli(env, "sync", "--json")
    assert p.returncode == 0, p.stderr
    snap_id = json.loads(p.stdout)["snapshot_page_id"]
    assert snap_id
    (mem / "MEMORY.md").write_text("CORRUPTED\n")
    staging = str(tmp_path / "staging")
    p = _run_cli(env, "restore", snap_id, staging)
    # exit 1: the restore completed but one file genuinely mismatches
    assert p.returncode == 1, p.stderr + p.stdout
    assert "byte-identical=0" in p.stdout
    assert "mismatches=1" in p.stdout
    with open(os.path.join(staging, "MEMORY.md")) as f:
        assert f.read() == "# Memory\n"
    # live file untouched by restore
    assert (mem / "MEMORY.md").read_text() == "CORRUPTED\n"


def test_cli_version_through_wrapper(tmp_path):
    env, _mem = _cli_env(tmp_path)
    p = _run_cli(env, "version")
    assert p.returncode == 0
    assert "notion-sync" in p.stdout
