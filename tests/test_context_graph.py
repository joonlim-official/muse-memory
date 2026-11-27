#!/usr/bin/env python3
"""Unit and integration tests for muse-memory Holistic Personal Context Graph DB."""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "lib"))

from context_graph import ContextGraph  # noqa: E402


class TestContextGraph(unittest.TestCase):
    def test_holistic_eight_source_topic_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "context_graph.db"
            mem = root / "memory"
            (mem / "topics").mkdir(parents=True)
            (mem / "people").mkdir(parents=True)
            (mem / "locations").mkdir(parents=True)

            (mem / "topics/soccer.md").write_text(
                "---\ntitle: Youth Soccer\naliases: MVLA, Mogility\n---\n# Youth Soccer\n\nSee `people/ian.md` and `locations/bellarmine.md`.\n",
                encoding="utf-8",
            )
            (mem / "people/ian.md").write_text("# Ian\n\nPlays MVLA soccer.\n", encoding="utf-8")
            (mem / "locations/bellarmine.md").write_text("# Bellarmine College Prep\n\nCamp venue.\n", encoding="utf-8")

            with ContextGraph(db) as g:
                # 1. Agent memory
                m_res = g.ingest_memory_tree(root)
                self.assertEqual(m_res["nodes"], 3)
                self.assertEqual(m_res["edges"], 2)

                # 2. Geo / Google Maps Timeline
                tl_res = g.ingest_timeline({
                    "places": [{"id": "bellarmine", "name": "Bellarmine College Prep", "tier": "Occasional"}],
                    "days": [{"date": "2026-11-27", "summary": "Mogility camp day 1", "places": ["bellarmine"], "topics": ["soccer"]}],
                })
                self.assertGreaterEqual(tl_res["edges"], 2)

                # 3-7. Voice note (Plaud), Email, Chat, Purchase (Shop), Photo context
                signals = [
                    {"node_type": "voice_note", "title": "Plaud debrief after camp", "summary": "Coach feedback on first touch.", "timestamp": "2026-11-27T12:30:00Z", "topics": ["soccer"], "people": ["ian"], "places": ["bellarmine"]},
                    {"node_type": "email", "title": "Mogility camp confirmation", "summary": "Schedule 9am-12pm Fri-Sun.", "timestamp": "2026-11-20T09:00:00Z", "topics": ["soccer"]},
                    {"node_type": "chat", "title": "WhatsApp carpool with coach", "summary": "Drop-off at east gate.", "timestamp": "2026-11-26T18:00:00Z", "topics": ["soccer"], "places": ["bellarmine"]},
                    {"node_type": "purchase", "title": "Nike Phantom turf cleats", "summary": "Shop order delivered, size 5Y.", "timestamp": "2026-11-18T14:00:00Z", "topics": ["soccer"], "people": ["ian"]},
                    {"node_type": "photo_event", "title": "Bellarmine scrimmage photos", "summary": "18 action shots uploaded.", "timestamp": "2026-11-27T13:00:00Z", "topics": ["soccer"], "places": ["bellarmine"]},
                ]
                for sig in signals:
                    g.ingest_event(sig)

                # Holistic query on topic "soccer" (or alias "MVLA") connects ALL 8 signal types
                ctx = g.query_context("MVLA", hops=2)
                by_type = ctx["by_type"]
                for expected_type in ("topic", "person", "place", "day", "voice_note", "email", "chat", "purchase", "photo_event"):
                    self.assertIn(expected_type, by_type, f"Missing {expected_type} in holistic topic context")

                # Re-ingestion is idempotent
                before = g.stats()["nodes"]
                g.ingest_memory_tree(root)
                self.assertEqual(g.stats()["nodes"], before)

                # FTS5 reserved keywords (NOT / OR / NEAR) must never crash query_context
                safe_res = g.query_context("not or near soccer")
                self.assertGreaterEqual(safe_res["total_connected"], 1)

    def test_refuses_secret_or_private_balance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with ContextGraph(Path(tmp) / "g.db") as g:
                with self.assertRaises(ValueError):
                    g.ingest_event({
                        "node_type": "purchase",
                        "title": "Bad record",
                        "summary": "My checking balance is $125,000.00",  # leakage-check:ignore-line
                    })


if __name__ == "__main__":
    unittest.main()
