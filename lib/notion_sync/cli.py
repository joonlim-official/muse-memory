"""Command-line interface for notion-sync.

Subcommands:
    init        first-time setup: map local files to Notion pages
    sync        full two-way sync (pull -> reconcile -> push -> snapshot)
    status      show the sync plan without writing anything
    restore     restore a dated snapshot into a staging directory
    version     print the package version

Exit codes:
    0  success (sync fully applied, or status clean)
    1  sync could not be fully applied (conflict, hold, block, deletion,
       or error) — nothing was written; resolve and re-run
    2  operational failure (config, transport, conversion, write)
"""

import argparse
import json
import os
import sys

from . import __version__
from .config import load_config, ConfigError
from .engine import Engine, SyncError, default_guard_check
from .transport import NotionTransport, TransportError


def _build_engine(args):
    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"notion-sync: configuration error: {e}", file=sys.stderr)
        raise SystemExit(2)
    transport = NotionTransport(cfg.api_key, cfg.api_base, cfg.api_version)
    guard = default_guard_check(cfg.guard_bin)
    if getattr(args, "no_guard", False):
        guard = lambda text: 0  # noqa: E731 — tests / emergencies only
    return Engine(cfg, transport, guard_check=guard)


def _print_report(report):
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))


def cmd_init(args):
    engine = _build_engine(args)
    try:
        code, report = engine.init()
    except (SyncError, TransportError) as e:
        print(f"notion-sync: init failed: {e}", file=sys.stderr)
        return 2
    _print_report(report)
    return code


def cmd_sync(args):
    engine = _build_engine(args)
    try:
        code, report = engine.sync()
    except (SyncError, TransportError) as e:
        print(f"notion-sync: sync failed: {e}", file=sys.stderr)
        return 2
    if args.json:
        _print_report(report)
    else:
        plan = report.get("plan", {})
        parts = [f"{k}={v}" for k, v in sorted(plan.items())]
        print("sync " + ("clean" if code == 0 else "not applied")
              + ": " + " ".join(parts))
        for key in ("conflicts", "deletions", "holds", "blocks", "errors"):
            items = report.get(key)
            if items:
                print(f"{key}:")
                for item in items:
                    print(f"  - {item}")
        note = report.get("note")
        if note:
            print(note)
    return code


def cmd_status(args):
    engine = _build_engine(args)
    try:
        plan, _local_files, _remote = engine.plan()
    except (SyncError, TransportError) as e:
        print(f"notion-sync: status failed: {e}", file=sys.stderr)
        return 2
    summary = plan.summary()
    if args.json:
        _print_report({"plan": summary,
                       "conflicts": plan.conflicts,
                       "deletions": plan.deletions,
                       "holds": plan.holds,
                       "blocks": plan.blocks,
                       "errors": plan.errors})
    else:
        parts = [f"{k}={v}" for k, v in sorted(summary.items())]
        print("plan: " + " ".join(parts))
        print("actionable:" if plan.actionable()
              else "NOT actionable — sync would write nothing")
    return 0 if plan.actionable() else 1


def cmd_restore(args):
    engine = _build_engine(args)
    staging = os.path.abspath(args.staging_dir)
    try:
        report = engine.restore(args.snapshot_page_id, staging)
    except (SyncError, TransportError) as e:
        print(f"notion-sync: restore failed: {e}", file=sys.stderr)
        return 2
    print(f"restored {report['total']} files to {staging}")
    print(f"byte-identical={report['byte_identical']} "
          f"equivalent={report['equivalent']} "
          f"mismatches={len(report['mismatches'])} "
          f"live-only={len(report['live_only'])}")
    for rel, reason in report["mismatches"]:
        print(f"  mismatch: {rel}: {reason}")
    return 0 if not report["mismatches"] else 1


def cmd_version(_args):
    print(f"notion-sync {__version__}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(
        prog="notion-sync",
        description="Two-way sync between muse-memory markdown files "
                    "and Notion (persistent live pages + dated snapshots).")
    p.add_argument("--no-guard", action="store_true",
                   help="skip the memory-guard scan (tests/emergencies only)")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="first-time setup")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("sync", help="full two-way sync")
    sp.add_argument("--json", action="store_true",
                    help="print the full report as JSON")
    sp.set_defaults(func=cmd_sync)

    sp = sub.add_parser("status", help="show the sync plan, write nothing")
    sp.add_argument("--json", action="store_true",
                    help="print the full plan as JSON")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("restore",
                        help="restore a dated snapshot to a staging dir")
    sp.add_argument("snapshot_page_id", help="Notion page ID of the snapshot")
    sp.add_argument("staging_dir", help="directory to restore into")
    sp.set_defaults(func=cmd_restore)

    sp = sub.add_parser("version", help="print the version")
    sp.set_defaults(func=cmd_version)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
