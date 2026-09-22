"""Three-way reconciliation engine for notion-sync.

Sync model per managed file (relpath under the memory root):

    base   = last successfully synced markdown (state/base/<relpath>)
    local  = current file on disk
    remote = current Notion page blocks, converted to markdown

Comparison uses canonical() (structural): formatting-only differences are
not changes. The decision matrix:

    local changed | remote changed | action
    --------------+----------------+-------------------------------
    no            | no             | clean
    yes           | no             | push local -> Notion (incremental)
    no            | yes            | pull Notion -> local (guard-scanned)
    yes           | yes            | CONFLICT: preserve both, write neither

Additionally:
    - mapped page archived/missing in Notion -> reported as deletion;
      the local file is preserved, never deleted.
    - unmapped hub child page titled like a valid relpath -> adopted as a
      new local file after route, collision, and guard validation.
    - local file with no mapping -> new Notion page created, content pushed.

All-or-nothing: the full plan (including every guard scan) is computed
first. If anything is a conflict, hold, block, deletion needing review,
or error, NOTHING is written — no local files, no Notion edits, no
snapshot, no state advancement. Only a fully actionable plan is applied,
in the order: pull remote edits -> push local edits -> adopt new pages ->
create dated recovery snapshot -> advance state transactionally.
"""

import fnmatch
import json
import os
import shutil
import subprocess
import tempfile

from . import markdown as md
from . import transport as tp
from .config import Config

# ---------------------------------------------------------------------------
# guard integration
# ---------------------------------------------------------------------------

GUARD_OK = 0        # clean
GUARD_SECRET = 1    # secrets found: hard block
GUARD_REVIEW = 2    # figures / personal data: human review required


def default_guard_check(guard_bin):
    """Build a guard callable that shells out to bin/memory-guard."""
    def check(text):
        try:
            proc = subprocess.run(
                [guard_bin], input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=60)
            return proc.returncode
        except FileNotFoundError:
            raise SyncError(f"guard binary not found: {guard_bin}")
        except subprocess.TimeoutExpired:
            raise SyncError(f"guard binary timed out: {guard_bin}")
    return check


class SyncError(Exception):
    """Operational failure: config, transport, conversion, or write."""


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------

def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


class SyncState:
    """Persistent sync state under config.state_dir."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        os.makedirs(cfg.state_dir, exist_ok=True)
        os.makedirs(cfg.base_dir, exist_ok=True)
        self.pages = _read_json(cfg.pages_file, {})            # rel -> page_id
        self.conflicts = _read_json(cfg.conflicts_file, [])    # [records]
        self.snapshots = _read_json(cfg.snapshots_file, {})    # date -> page_id
        self.deletions = _read_json(cfg.deletions_file, {})    # rel -> record

    # -- base snapshots (the "base" of the three-way merge) ----------------
    def base_path(self, rel):
        # keep directory structure under base/ for debuggability
        return os.path.join(self.cfg.base_dir, rel)

    def read_base(self, rel):
        try:
            with open(self.base_path(rel), "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def _stage_base(self, stage_dir, rel, text):
        dest = os.path.join(stage_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(text)

    def commit_base(self, staged):
        """Atomically swap the staged base dir into place."""
        final = self.cfg.base_dir
        backup = final + ".prev"
        if os.path.isdir(backup):
            shutil.rmtree(backup)
        if os.path.isdir(final):
            os.rename(final, backup)
        os.rename(staged, final)
        shutil.rmtree(backup, ignore_errors=True)

    # -- persistence -------------------------------------------------------
    def save(self):
        _write_json_atomic(self.cfg.pages_file, self.pages)
        _write_json_atomic(self.cfg.conflicts_file, self.conflicts)
        _write_json_atomic(self.cfg.snapshots_file, self.snapshots)
        _write_json_atomic(self.cfg.deletions_file, self.deletions)


# ---------------------------------------------------------------------------
# adoption routing validation
# ---------------------------------------------------------------------------

_ENTITY_DIRS = ("people", "groups", "topics", "meetings", "activities",
                "interests", "locations", "trace", "bank")


def validate_adoption_relpath(rel, memory_root):
    """Check a candidate relpath from a Notion page title.

    Returns the normalized relpath, or an error string.
    """
    if not rel or not rel.endswith(".md"):
        return None, "title is not a markdown path"
    if os.path.isabs(rel):
        return None, "absolute paths are not adopted"
    norm = os.path.normpath(rel)
    if norm.startswith("..") or ".." in norm.split(os.sep):
        return None, "path traversal is not adopted"
    # resolve against the memory root and confirm containment
    abs_path = os.path.realpath(os.path.join(memory_root, norm))
    root_real = os.path.realpath(memory_root)
    if abs_path != root_real and not abs_path.startswith(root_real + os.sep):
        return None, "path escapes the memory root"
    parts = norm.split(os.sep)
    if parts[0] == "memory" and len(parts) > 2 and parts[1] not in _ENTITY_DIRS:
        # allow memory/<date>.md and memory/INDEX.md, entity dirs, and
        # memory/<entity-dir>/... only
        if not (len(parts) == 2):
            return None, f"unknown entity directory: memory/{parts[1]}"
    return norm, None


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------

SNAPSHOT_TITLE_PREFIX = "Memory backup \u2014 "  # "Memory backup — YYYY-MM-DD"


class Plan:
    def __init__(self):
        self.push = []        # relpaths: local-only change -> Notion
        self.pull = []        # relpaths: remote-only change -> local
        self.new_local = []   # relpaths: local file, no page yet -> create
        self.adopt = []       # (page_id, relpath): new Notion page -> local
        self.conflicts = []   # relpaths: both changed
        self.deletions = []   # relpaths: page archived/missing remotely
        self.holds = []       # (relpath, reason): guard exit 2
        self.blocks = []      # (relpath, reason): guard exit 1
        self.errors = []      # (relpath, message): conversion/transport/write
        self.clean = 0

    def actionable(self):
        return not (self.conflicts or self.holds or self.blocks
                    or self.errors or self.deletions)

    def summary(self):
        return {
            "push": len(self.push), "pull": len(self.pull),
            "new_local": len(self.new_local), "adopt": len(self.adopt),
            "conflicts": len(self.conflicts),
            "deletions": len(self.deletions),
            "holds": len(self.holds), "blocks": len(self.blocks),
            "errors": len(self.errors), "clean": self.clean,
        }


class Engine:
    def __init__(self, cfg: Config, transport, guard_check=None):
        self.cfg = cfg
        self.tp = transport
        self.guard = guard_check or default_guard_check(cfg.guard_bin)
        self.state = SyncState(cfg)

    # -- discovery ------------------------------------------------------
    def discover_local(self):
        """All managed markdown files, keyed by relpath (posix)."""
        mem_dir = os.path.join(self.cfg.memory_root, "memory")
        found = {}
        for dirpath, dirnames, filenames in os.walk(self.cfg.memory_root):
            # never descend into the state dir or hidden dirs
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".") and d != "__pycache__"]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                abs_p = os.path.join(dirpath, fn)
                rel = os.path.relpath(abs_p, self.cfg.memory_root)
                rel = rel.replace(os.sep, "/")
                if any(fnmatch.fnmatch(rel, pat) for pat in self.cfg.exclude):
                    continue
                # only manage files under memory/ plus the top-level curated
                # files (MEMORY.md); skip everything else at the root
                if "/" in rel and not rel.startswith("memory/"):
                    continue
                found[rel] = abs_p
        # drop anything inside the state dir (belt and braces)
        state_rel = os.path.relpath(self.cfg.state_dir,
                                    self.cfg.memory_root).replace(os.sep, "/")
        found = {r: p for r, p in found.items()
                 if r != state_rel and not r.startswith(state_rel + "/")}
        return found

    def read_local(self, abs_p):
        with open(abs_p, "r", encoding="utf-8") as f:
            return f.read()

    # -- remote pull ----------------------------------------------------
    def pull_remote(self):
        """Return {relpath: (page_id, blocks)} plus (unmapped_pages, errors).

        unmapped_pages: [(page_id, title)] for hub children with no mapping
        and which are not known snapshot pages.
        """
        mapped = {}
        errors = []
        snapshot_ids = set(self.state.snapshots.values())
        mapped_ids = set(self.state.pages.values())

        for rel, page_id in sorted(self.state.pages.items()):
            try:
                page = self.tp.get_page(page_id)
            except tp.NotFound:
                errors.append((rel, "not-found"))
                continue
            except tp.TransportError as e:
                raise SyncError(f"pull failed for {rel}: {e}")
            if page.get("archived"):
                errors.append((rel, "archived"))
                continue
            try:
                api_blocks = self.tp.get_blocks(page_id)
            except tp.TransportError as e:
                raise SyncError(f"pull failed for {rel}: {e}")
            try:
                blocks = tp.notion_to_blocks(api_blocks)
            except Exception as e:
                errors.append((rel, f"conversion failed: {e}"))
                continue
            mapped[rel] = (page_id, blocks)

        unmapped = []
        try:
            children = self.tp.list_child_pages(self.cfg.hub_id)
        except tp.TransportError as e:
            raise SyncError(f"could not list hub children: {e}")
        for ch in children:
            if ch["archived"]:
                continue
            if ch["id"] in mapped_ids or ch["id"] in snapshot_ids:
                continue
            if ch["title"].startswith(SNAPSHOT_TITLE_PREFIX):
                continue
            unmapped.append((ch["id"], ch["title"]))
        return mapped, unmapped, errors

    # -- planning -------------------------------------------------------
    def plan(self):
        """Compute the full sync plan. No writes happen here."""
        local_files = self.discover_local()
        remote, unmapped, pull_errors = self.pull_remote()
        plan = Plan()
        for rel, reason in pull_errors:
            if reason in ("not-found", "archived"):
                if rel not in self.state.deletions:
                    plan.deletions.append(rel)
            else:
                plan.errors.append((rel, reason))

        # three-way compare for every mapped file present on both sides
        for rel in sorted(set(local_files) & set(remote)):
            page_id, blocks = remote[rel]
            try:
                local_text = self.read_local(local_files[rel])
            except OSError as e:
                plan.errors.append((rel, f"read failed: {e}"))
                continue
            base_text = self.state.read_base(rel)
            if base_text is None:
                # mapped but no base: treat as both-changed -> conflict is
                # wrong; instead push local (source of truth) after a pull
                # comparison against remote content.
                plan.push.append(rel)
                continue
            try:
                c_local = md.canonical_text(local_text)
                c_base = md.canonical_text(base_text)
                remote_text = md.blocks_to_markdown(blocks)
                c_remote = md.canonical_text(remote_text)
            except Exception as e:
                plan.errors.append((rel, f"conversion failed: {e}"))
                continue
            local_changed = c_local != c_base
            remote_changed = c_remote != c_base
            if not local_changed and not remote_changed:
                plan.clean += 1
            elif local_changed and not remote_changed:
                plan.push.append(rel)
            elif remote_changed and not local_changed:
                verdict = self._guard_incoming(rel, remote_text)
                if verdict == GUARD_OK:
                    plan.pull.append(rel)
                elif verdict == GUARD_SECRET:
                    plan.blocks.append((rel, "incoming content blocked by guard"))
                else:
                    plan.holds.append((rel, "incoming content needs human review"))
            else:
                plan.conflicts.append(rel)

        # local files with no mapping -> create pages
        for rel in sorted(set(local_files) - set(remote)
                          - {r for r, _ in plan.errors}):
            if rel in self.state.pages:
                # mapped but page errored above; already recorded
                continue
            plan.new_local.append(rel)

        # unmapped hub children -> adoption candidates
        seen_titles = {}
        for page_id, title in unmapped:
            rel, err = validate_adoption_relpath(title, self.cfg.memory_root)
            if err:
                plan.errors.append((title, f"not adopted: {err}"))
                continue
            if rel in local_files or rel in self.state.pages:
                plan.errors.append(
                    (title, f"not adopted: collides with existing {rel}"))
                continue
            if rel in seen_titles:
                plan.errors.append(
                    (title, "not adopted: duplicate title in hub"))
                continue
            seen_titles[rel] = page_id
            try:
                api_blocks = self.tp.get_blocks(page_id)
                blocks = tp.notion_to_blocks(api_blocks)
                text = md.blocks_to_markdown(blocks)
            except Exception as e:
                plan.errors.append((title, f"conversion failed: {e}"))
                continue
            verdict = self._guard_incoming(title, text)
            if verdict == GUARD_OK:
                plan.adopt.append((page_id, rel))
            elif verdict == GUARD_SECRET:
                plan.blocks.append((title, "incoming content blocked by guard"))
            else:
                plan.holds.append((title, "incoming content needs human review"))

        # outgoing guard scan for pushes (fail-closed on secrets)
        for rel in list(plan.push):
            try:
                text = self.read_local(local_files[rel])
            except OSError as e:
                plan.errors.append((rel, f"read failed: {e}"))
                plan.push.remove(rel)
                continue
            verdict = self._guard_outgoing(rel, text)
            if verdict == GUARD_SECRET:
                plan.blocks.append((rel, "outgoing content blocked by guard"))
                plan.push.remove(rel)
            elif verdict == GUARD_REVIEW:
                plan.holds.append((rel, "outgoing content needs human review"))
                plan.push.remove(rel)
        for rel in list(plan.new_local):
            try:
                text = self.read_local(local_files[rel])
            except OSError as e:
                plan.errors.append((rel, f"read failed: {e}"))
                plan.new_local.remove(rel)
                continue
            verdict = self._guard_outgoing(rel, text)
            if verdict == GUARD_SECRET:
                plan.blocks.append((rel, "outgoing content blocked by guard"))
                plan.new_local.remove(rel)
            elif verdict == GUARD_REVIEW:
                plan.holds.append((rel, "outgoing content needs human review"))
                plan.new_local.remove(rel)

        return plan, local_files, remote

    def _guard_incoming(self, _rel, text):
        try:
            return self.guard(text)
        except SyncError:
            raise
        except Exception as e:
            raise SyncError(f"guard check failed: {e}")

    def _guard_outgoing(self, _rel, text):
        return self._guard_incoming(_rel, text)

    # -- apply ----------------------------------------------------------
    def apply(self, plan, local_files, remote):
        """Apply a fully actionable plan. Returns a report dict.

        Raises SyncError mid-apply on write failure; state is only
        advanced after every step succeeds.
        """
        report = {"pulled": [], "pushed": [], "created": [], "adopted": []}

        # 1. pull remote-only changes (guard already passed in plan())
        for rel in plan.pull:
            _page_id, blocks = remote[rel]
            text = md.blocks_to_markdown(blocks)
            self._write_local(local_files[rel], text)
            report["pulled"].append(rel)

        # 2. push local-only changes (incremental page updates)
        for rel in plan.push:
            page_id = self.state.pages[rel]
            text = self.read_local(local_files[rel])
            blocks = md.parse_markdown(text)
            self.tp.replace_blocks(page_id, blocks)
            report["pushed"].append(rel)

        # 3. create pages for new local files
        for rel in plan.new_local:
            text = self.read_local(local_files[rel])
            blocks = md.parse_markdown(text)
            page_id = self.tp.create_page(self.cfg.hub_id, rel)
            self.tp.replace_blocks(page_id, blocks)
            self.state.pages[rel] = page_id
            report["created"].append(rel)

        # 4. adopt new Notion pages as local files
        for page_id, rel in plan.adopt:
            api_blocks = self.tp.get_blocks(page_id)
            blocks = tp.notion_to_blocks(api_blocks)
            text = md.blocks_to_markdown(blocks)
            abs_p = os.path.join(self.cfg.memory_root, rel)
            os.makedirs(os.path.dirname(abs_p), exist_ok=True)
            self._write_local(abs_p, text)
            self.state.pages[rel] = page_id
            local_files[rel] = abs_p
            report["adopted"].append(rel)

        # 5. dated recovery snapshot (only after all edits succeeded)
        snapshot_id = self.create_snapshot(local_files)

        # 6. advance state transactionally: base dir swap + json writes
        stage = tempfile.mkdtemp(prefix="notion-sync-base-",
                                 dir=self.cfg.state_dir)
        try:
            for rel, abs_p in local_files.items():
                if rel in self.state.pages:
                    self.state._stage_base(stage, rel, self.read_local(abs_p))
            self.state.commit_base(stage)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        self.state.save()
        report["snapshot_page_id"] = snapshot_id
        return report

    def _write_local(self, abs_p, text):
        tmp = abs_p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, abs_p)

    # -- snapshot -------------------------------------------------------
    def local_date(self):
        from datetime import datetime, timezone
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(self.cfg.tz)
        except Exception:
            tz = timezone.utc
        return datetime.now(tz).strftime("%Y-%m-%d")

    def create_snapshot(self, local_files):
        """Create a dated recovery snapshot page under the hub."""
        date = self.local_date()
        title = SNAPSHOT_TITLE_PREFIX + date
        # one snapshot per date: reuse if this run already made one
        if date in self.state.snapshots:
            return self.state.snapshots[date]
        snap_id = self.tp.create_page(self.cfg.hub_id, title)
        for rel in sorted(local_files):
            if rel not in self.state.pages:
                continue
            text = self.read_local(local_files[rel])
            blocks = md.parse_markdown(text)
            child_id = self.tp.create_page(snap_id, rel)
            self.tp.replace_blocks(child_id, blocks)
        self.state.snapshots[date] = snap_id
        return snap_id

    # -- restore --------------------------------------------------------
    def restore(self, snapshot_page_id, staging_dir):
        """Restore a snapshot into a staging dir. Never touches live files.

        Returns a report with exact accounting: total files, byte-identical,
        canonically equivalent, genuine mismatches, live-only files.
        """
        os.makedirs(staging_dir, exist_ok=True)
        try:
            children = self.tp.list_child_pages(snapshot_page_id)
        except tp.TransportError as e:
            raise SyncError(f"cannot read snapshot page: {e}")
        report = {"total": 0, "byte_identical": 0, "equivalent": 0,
                  "mismatches": [], "live_only": [], "restored": []}
        live = self.discover_local()
        restored_rels = []
        for ch in sorted(children, key=lambda c: c["title"]):
            if ch["archived"]:
                continue
            rel, err = validate_adoption_relpath(ch["title"],
                                                 self.cfg.memory_root)
            if err:
                report["mismatches"].append(
                    (ch["title"], f"invalid snapshot child: {err}"))
                continue
            try:
                api_blocks = self.tp.get_blocks(ch["id"])
                blocks = tp.notion_to_blocks(api_blocks)
                text = md.blocks_to_markdown(blocks)
            except Exception as e:
                report["mismatches"].append((rel, f"conversion failed: {e}"))
                continue
            dest = os.path.join(staging_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)
            restored_rels.append(rel)
            report["total"] += 1
            report["restored"].append(rel)
            live_path = live.get(rel)
            if live_path is None or not os.path.exists(live_path):
                report["live_only"].append(rel)  # in snapshot, not in live
                continue
            with open(live_path, "r", encoding="utf-8") as f:
                live_text = f.read()
            if live_text == text:
                report["byte_identical"] += 1
            elif md.canonical_text(live_text) == md.canonical_text(text):
                report["equivalent"] += 1
            else:
                report["mismatches"].append((rel, "content differs"))
        for rel in sorted(set(live) - set(restored_rels)):
            report["live_only"].append(rel)
        # de-dupe live_only while keeping order
        seen = set()
        report["live_only"] = [r for r in report["live_only"]
                               if not (r in seen or seen.add(r))]
        return report

    # -- top-level commands ----------------------------------------------
    def sync(self):
        """Full sync: plan, then apply only if fully actionable."""
        plan, local_files, remote = self.plan()
        if not plan.actionable():
            self._record_conflicts(plan)
            self._record_deletions(plan)
            self.state.save()
            return 1, {"plan": plan.summary(),
                       "conflicts": plan.conflicts,
                       "deletions": plan.deletions,
                       "holds": plan.holds, "blocks": plan.blocks,
                       "errors": plan.errors,
                       "note": "no writes performed; resolve and re-run"}
        try:
            report = self.apply(plan, local_files, remote)
        except (tp.TransportError, OSError, SyncError) as e:
            raise SyncError(f"apply failed: {e}")
        self._record_deletions(plan)
        report["plan"] = plan.summary()
        return 0, report

    def _record_conflicts(self, plan):
        for rel in plan.conflicts:
            rec = {"relpath": rel, "page_id": self.state.pages.get(rel)}
            if rec not in self.state.conflicts:
                self.state.conflicts.append(rec)

    def _record_deletions(self, plan):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        for rel in plan.deletions:
            self.state.deletions[rel] = {
                "page_id": self.state.pages.get(rel),
                "reported_at": now,
            }

    def init(self):
        """First-time setup: map local files to hub pages, push content.

        For each managed file: if a hub child page already has the relpath
        as its title, adopt the mapping without overwriting; otherwise
        create the page and push the file's content. Establishes the base
        snapshots so the next sync is a no-op.
        """
        local_files = self.discover_local()
        try:
            children = self.tp.list_child_pages(self.cfg.hub_id)
        except tp.TransportError as e:
            raise SyncError(f"could not list hub children: {e}")
        by_title = {c["title"]: c["id"] for c in children
                    if not c["archived"]}
        report = {"mapped": [], "created": [], "adopted_existing": []}
        for rel in sorted(local_files):
            if rel in self.state.pages:
                report["mapped"].append(rel)
                continue
            text = self.read_local(local_files[rel])
            verdict = self._guard_outgoing(rel, text)
            if verdict != GUARD_OK:
                raise SyncError(
                    f"init blocked for {rel}: guard exit {verdict}")
            blocks = md.parse_markdown(text)
            if rel in by_title:
                page_id = by_title[rel]
                self.state.pages[rel] = page_id
                report["adopted_existing"].append(rel)
            else:
                page_id = self.tp.create_page(self.cfg.hub_id, rel)
                self.tp.replace_blocks(page_id, blocks)
                self.state.pages[rel] = page_id
                report["created"].append(rel)
        stage = tempfile.mkdtemp(prefix="notion-sync-base-",
                                 dir=self.cfg.state_dir)
        try:
            for rel, abs_p in local_files.items():
                if rel in self.state.pages:
                    self.state._stage_base(stage, rel, self.read_local(abs_p))
            self.state.commit_base(stage)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        self.state.save()
        return 0, report
