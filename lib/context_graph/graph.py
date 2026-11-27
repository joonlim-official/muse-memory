"""SQLite3 + FTS5 Holistic Personal Context Graph DB for muse-memory.

Unifies eight personal signal streams into one local graph:
  1. geo / Google Maps Timeline  (day, place, VISITED)
  2. agent memory                (memory_page, topic, person, group, place)
  3. voice recording notes       (voice_note — e.g. Plaud transcripts/summaries)
  4. email                       (email — Primary / Updates / Forums)
  5. chat                        (chat — WhatsApp / messages)
  6. purchase data               (purchase — Shop / orders / warranties; no bank balances)
  7. photo context               (photo_event — Google Photos / iCloud events)
  8. context / calendar events   (event — calendar meetings, trips, milestones)

Zero third-party dependencies (Python 3 stdlib sqlite3).
"""

import datetime
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path

from .embeddings import (
    choose_backend,
    content_hash as embed_content_hash,
    cosine_similarity,
    embed_text,
    pack_vector,
    unpack_vector,
)

DEFAULT_DB_NAME = "context_graph.db"

NODE_TYPES = {
    "topic",
    "person",
    "group",
    "place",
    "day",
    "event",
    "voice_note",
    "email",
    "chat",
    "purchase",
    "photo_event",
    "memory_page",
}

EDGE_RELATIONS = {
    "VISITED",
    "TOUCHES",
    "INVOLVES",
    "AT_PLACE",
    "ON_DAY",
    "MENTIONS",
    "DERIVED_FROM",
    "RELATED_TO",
}

SECRET_OR_BALANCE_RE = re.compile(
    r"(?:\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"
    r"|\b(?:sk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,})\b"
    r"|\bAIza[0-9A-Za-z_-]{30,}\b"
    r"|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\b(?:checking|savings|brokerage|net\s+worth|401k|ira|balance)\b[^\n]{0,40}\$[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?"
    r"|\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b)",
    re.IGNORECASE,
)

COVERS_RE = re.compile(r"^(?:covers|aliases)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
LINK_RE = re.compile(r"`((?:~/memory/)?(?:people|groups|topics|locations)/[a-z0-9_./-]+\.md)`")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(raw: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    return s[:64] or hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def _check_safe(text: str) -> None:
    if SECRET_OR_BALANCE_RE.search(text):
        raise ValueError("Refused: payload contains a secret, SSN, or private account balance.")


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip().strip("\"'[]")
    return meta, text[end + 4 :].lstrip("\n")


class ContextGraph:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "ContextGraph":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                aliases TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                timestamp TEXT NOT NULL DEFAULT '',
                ref_path TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS edges (
                src_id TEXT NOT NULL,
                dst_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                timestamp TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'manual',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (src_id, dst_id, relation),
                FOREIGN KEY (src_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (dst_id) REFERENCES nodes(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
            CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id);
            CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                id UNINDEXED,
                title,
                aliases,
                summary
            );

            CREATE TABLE IF NOT EXISTS ingest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                nodes_upserted INTEGER NOT NULL,
                edges_upserted INTEGER NOT NULL,
                ran_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS node_embeddings (
                node_id TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                model TEXT NOT NULL,
                dims INTEGER NOT NULL,
                vector_blob BLOB NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()

    def upsert_node(
        self,
        node_id: str,
        node_type: str,
        title: str,
        summary: str = "",
        aliases: str = "",
        source: str = "manual",
        timestamp: str = "",
        ref_path: str = "",
        metadata: dict[str, object] | None = None,
    ) -> str:
        if node_type not in NODE_TYPES:
            raise ValueError(f"Unsupported node_type: {node_type!r}")
        _check_safe(f"{title}\n{summary}\n{aliases}\n{json.dumps(metadata or {})}")

        now = _now_iso()
        meta_json = json.dumps(metadata or {}, sort_keys=True)
        self.conn.execute(
            """
            INSERT INTO nodes (id, node_type, title, summary, aliases, source, timestamp, ref_path, metadata_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                node_type=excluded.node_type,
                title=excluded.title,
                summary=CASE WHEN excluded.summary != '' THEN excluded.summary ELSE nodes.summary END,
                aliases=CASE WHEN excluded.aliases != '' THEN excluded.aliases ELSE nodes.aliases END,
                source=excluded.source,
                timestamp=CASE WHEN excluded.timestamp != '' THEN excluded.timestamp ELSE nodes.timestamp END,
                ref_path=CASE WHEN excluded.ref_path != '' THEN excluded.ref_path ELSE nodes.ref_path END,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            (node_id, node_type, title.strip(), summary.strip(), aliases.strip(), source, timestamp, ref_path, meta_json, now),
        )
        self.conn.execute("DELETE FROM nodes_fts WHERE id = ?", (node_id,))
        self.conn.execute(
            "INSERT INTO nodes_fts (id, title, aliases, summary) VALUES (?, ?, ?, ?)",
            (node_id, title.strip(), aliases.strip(), summary.strip()),
        )
        return node_id

    def upsert_edge(
        self,
        src_id: str,
        dst_id: str,
        relation: str,
        weight: float = 1.0,
        timestamp: str = "",
        source: str = "manual",
        metadata: dict[str, object] | None = None,
    ) -> None:
        if relation not in EDGE_RELATIONS:
            raise ValueError(f"Unsupported edge relation: {relation!r}")
        now = _now_iso()
        self.conn.execute(
            """
            INSERT INTO edges (src_id, dst_id, relation, weight, timestamp, source, metadata_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(src_id, dst_id, relation) DO UPDATE SET
                weight=MAX(edges.weight, excluded.weight),
                timestamp=CASE WHEN excluded.timestamp != '' THEN excluded.timestamp ELSE edges.timestamp END,
                source=excluded.source,
                metadata_json=excluded.metadata_json,
                updated_at=excluded.updated_at
            """,
            (src_id, dst_id, relation, weight, timestamp, source, json.dumps(metadata or {}, sort_keys=True), now),
        )

    def record_ingest(self, source: str, nodes_n: int, edges_n: int) -> None:
        self.conn.execute(
            "INSERT INTO ingest_runs (source, nodes_upserted, edges_upserted, ran_at) VALUES (?, ?, ?, ?)",
            (source, nodes_n, edges_n, _now_iso()),
        )
        self.conn.commit()

    def ingest_memory_tree(self, memory_root: Path) -> dict[str, int]:
        """Ingest curated memory pages (people, groups, topics, locations) and their cross-links."""
        mem_dir = memory_root / "memory" if (memory_root / "memory").is_dir() else memory_root
        dir_map = {"people": "person", "groups": "group", "topics": "topic", "locations": "place"}

        nodes_n = 0
        edges_n = 0
        pending_links: list[tuple[str, str]] = []

        for folder, ntype in dir_map.items():
            sub = mem_dir / folder
            if not sub.is_dir():
                continue
            for md in sorted(sub.glob("*.md")):
                if md.name == "INDEX.md":
                    continue
                raw = md.read_text(encoding="utf-8", errors="replace")
                if SECRET_OR_BALANCE_RE.search(raw):
                    continue
                meta, body = _parse_front_matter(raw)
                h1_m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
                title = meta.get("title") or (h1_m.group(1).strip() if h1_m else md.stem.replace("-", " ").title())
                covers = " ".join(COVERS_RE.findall(body[:1000]))
                aliases = " ".join(x for x in (meta.get("aliases", ""), meta.get("covers", ""), covers) if x).strip()
                first_para = " ".join(
                    l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#") and not l.lower().startswith("covers:")
                )[:280]
                nid = f"{ntype}:{md.stem}"
                self.upsert_node(
                    nid,
                    ntype,
                    title,
                    summary=first_para,
                    aliases=aliases,
                    source="agent_memory",
                    ref_path=f"{folder}/{md.name}",
                )
                nodes_n += 1
                for ref in LINK_RE.findall(raw):
                    rel = ref.removeprefix("~/memory/")
                    parts = Path(rel).parts
                    if len(parts) >= 2 and parts[0] in dir_map:
                        dst_id = f"{dir_map[parts[0]]}:{Path(parts[-1]).stem}"
                        if dst_id != nid:
                            pending_links.append((nid, dst_id))

        existing_ids = {r[0] for r in self.conn.execute("SELECT id FROM nodes").fetchall()}
        for src_id, dst_id in pending_links:
            if src_id in existing_ids and dst_id in existing_ids:
                self.upsert_edge(src_id, dst_id, "MENTIONS", source="agent_memory")
                edges_n += 1

        self.record_ingest("agent_memory", nodes_n, edges_n)
        return {"nodes": nodes_n, "edges": edges_n}

    def ingest_timeline(self, timeline_data: dict[str, object]) -> dict[str, int]:
        """Ingest Google Maps Timeline index JSON: {'places': [...], 'days': [...]}."""
        nodes_n = 0
        edges_n = 0
        for p in timeline_data.get("places", []) or []:
            if not isinstance(p, dict):
                continue
            pid = f"place:{_slug(str(p.get('id') or p.get('name', 'unknown')))}"
            self.upsert_node(
                pid,
                "place",
                str(p.get("name") or pid),
                summary=str(p.get("address") or p.get("tier") or ""),
                aliases=str(p.get("aliases") or ""),
                source="google_maps_timeline",
                metadata={"lat": p.get("lat"), "lng": p.get("lng"), "tier": p.get("tier")},
            )
            nodes_n += 1

        for d in timeline_data.get("days", []) or []:
            if not isinstance(d, dict) or not d.get("date"):
                continue
            date_str = str(d["date"])
            did = f"day:{date_str}"
            self.upsert_node(
                did,
                "day",
                date_str,
                summary=str(d.get("summary") or ""),
                source="google_maps_timeline",
                timestamp=date_str,
            )
            nodes_n += 1
            for place_ref in d.get("places", []) or []:
                pid = f"place:{_slug(str(place_ref))}"
                if not self.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (pid,)).fetchone():
                    self.upsert_node(pid, "place", str(place_ref), source="google_maps_timeline")
                    nodes_n += 1
                self.upsert_edge(did, pid, "VISITED", timestamp=date_str, source="google_maps_timeline")
                edges_n += 1
            for topic_ref in d.get("topics", []) or []:
                tid = f"topic:{_slug(str(topic_ref))}"
                if not self.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (tid,)).fetchone():
                    self.upsert_node(tid, "topic", str(topic_ref), source="google_maps_timeline")
                    nodes_n += 1
                self.upsert_edge(did, tid, "TOUCHES", timestamp=date_str, source="google_maps_timeline")
                edges_n += 1

        self.record_ingest("google_maps_timeline", nodes_n, edges_n)
        return {"nodes": nodes_n, "edges": edges_n}

    def ingest_event(self, payload: dict[str, object]) -> dict[str, object]:
        """Ingest a single multi-source signal (voice_note, email, chat, purchase, photo_event, event)."""
        ntype = str(payload.get("node_type", "")).strip()
        if ntype not in {"voice_note", "email", "chat", "purchase", "photo_event", "event"}:
            raise ValueError(f"Event node_type must be one of voice_note/email/chat/purchase/photo_event/event, got {ntype!r}")

        title = str(payload.get("title", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        if not title:
            raise ValueError("Event requires non-empty 'title'")
        raw_id = str(payload.get("id") or f"{ntype}:{_slug(title)}-{hashlib.sha256(summary.encode('utf-8')).hexdigest()[:6]}")
        if ":" not in raw_id:
            raw_id = f"{ntype}:{_slug(raw_id)}"

        ts = str(payload.get("timestamp") or payload.get("date") or "")
        source = str(payload.get("source") or ntype)
        ref_path = str(payload.get("ref_path") or payload.get("url") or "")
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

        self.upsert_node(raw_id, ntype, title, summary=summary, source=source, timestamp=ts, ref_path=ref_path, metadata=meta)
        edges_n = 0

        # Auto-link Day
        date_m = re.match(r"^(20\d{2}-\d{2}-\d{2})", ts)
        if date_m:
            day_str = date_m.group(1)
            did = f"day:{day_str}"
            if not self.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (did,)).fetchone():
                self.upsert_node(did, "day", day_str, source=source, timestamp=day_str)
            self.upsert_edge(raw_id, did, "ON_DAY", timestamp=ts, source=source)
            edges_n += 1

        # Auto-link Topics, People, Places
        for topic in payload.get("topics", []) or []:
            tid = f"topic:{_slug(str(topic))}"
            if not self.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (tid,)).fetchone():
                self.upsert_node(tid, "topic", str(topic), source=source)
            self.upsert_edge(raw_id, tid, "TOUCHES", timestamp=ts, source=source)
            edges_n += 1

        for person in payload.get("people", []) or []:
            pid = f"person:{_slug(str(person))}"
            if not self.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (pid,)).fetchone():
                self.upsert_node(pid, "person", str(person), source=source)
            self.upsert_edge(raw_id, pid, "INVOLVES", timestamp=ts, source=source)
            edges_n += 1

        for place in payload.get("places", []) or []:
            plid = f"place:{_slug(str(place))}"
            if not self.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (plid,)).fetchone():
                self.upsert_node(plid, "place", str(place), source=source)
            self.upsert_edge(raw_id, plid, "AT_PLACE", timestamp=ts, source=source)
            edges_n += 1

        self.record_ingest(source, 1, edges_n)
        return {"node_id": raw_id, "edges": edges_n}

    def embed_all_nodes(self, backend: str = "auto") -> dict[str, object]:
        """Incrementally embed all nodes whose content hash changed (never re-embeds unchanged nodes)."""
        chosen = choose_backend(backend)
        rows = self.conn.execute("SELECT id, title, aliases, summary FROM nodes").fetchall()
        existing = {
            str(r["node_id"]): (str(r["content_hash"]), str(r["model"]))
            for r in self.conn.execute("SELECT node_id, content_hash, model FROM node_embeddings").fetchall()
        }
        embedded = 0
        skipped = 0
        model_label = ""
        for r in rows:
            nid = str(r["id"])
            text = f"{r['title']} {r['aliases']} {r['summary']}".strip()
            if not text:
                skipped += 1
                continue
            chash = embed_content_hash(text)
            prev = existing.get(nid)
            if prev and prev[0] == chash and prev[1].startswith(f"{chosen}:"):
                skipped += 1
                continue
            vec, model_label = embed_text(text, backend=chosen)
            self.conn.execute(
                """
                INSERT INTO node_embeddings (node_id, content_hash, model, dims, vector_blob, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    content_hash=excluded.content_hash,
                    model=excluded.model,
                    dims=excluded.dims,
                    vector_blob=excluded.vector_blob,
                    updated_at=excluded.updated_at
                """,
                (nid, chash, model_label, len(vec), pack_vector(vec), _now_iso()),
            )
            embedded += 1
        self.conn.commit()
        return {"backend": chosen, "model": model_label, "embedded": embedded, "skipped": skipped}

    def _semantic_anchors(self, query: str, backend: str = "auto", top_k: int = 3, min_sim: float = 0.25) -> list[tuple[sqlite3.Row, float]]:
        stored = self.conn.execute("SELECT node_id, model, vector_blob FROM node_embeddings").fetchall()
        if not stored:
            return []
        # Match query embedding backend to stored vectors' prefix
        first_model = str(stored[0]["model"])
        vec_backend = "gemini" if first_model.startswith("gemini:") else "local"
        if backend in ("gemini", "local") and backend != vec_backend:
            vec_backend = backend
        try:
            q_vec, q_model = embed_text(query, backend=vec_backend)
        except RuntimeError:
            return []
        scored: list[tuple[float, str]] = []
        for r in stored:
            if str(r["model"]) != q_model:
                continue
            sim = cosine_similarity(q_vec, unpack_vector(bytes(r["vector_blob"])))
            if sim >= min_sim:
                scored.append((sim, str(r["node_id"])))
        scored.sort(reverse=True)
        out: list[tuple[sqlite3.Row, float]] = []
        for sim, nid in scored[:top_k]:
            row = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (nid,)).fetchone()
            if row:
                out.append((row, round(sim, 4)))
        return out

    def query_context(
        self,
        query: str,
        hops: int = 2,
        limit: int = 40,
        semantic_fallback: bool = True,
        min_sim: float = 0.25,
    ) -> dict[str, object]:
        """Assemble holistic topic context across all connected signal sources (lexical first, semantic fallback)."""
        q_clean = query.strip()
        anchors: list[sqlite3.Row] = []
        anchor_meta: dict[str, dict[str, object]] = {}

        # 1. Exact ID or slug match first
        exact_slug = _slug(q_clean)
        for r in self.conn.execute(
            "SELECT * FROM nodes WHERE id = ? OR id LIKE ? OR lower(title) = lower(?) LIMIT 5",
            (q_clean, f"%:{exact_slug}", q_clean),
        ).fetchall():
            anchors.append(r)
            anchor_meta[str(r["id"])] = {"matched_by": "exact"}

        # 2. FTS5 search fallback / expansion (quote every token so FTS5 keywords like NOT/OR/NEAR never crash)
        if not anchors:
            fts_terms = " OR ".join(f'"{t}"' for t in re.findall(r"[A-Za-z0-9]+", q_clean))
            if fts_terms:
                for r in self.conn.execute(
                    """
                    SELECT n.* FROM nodes_fts f
                    JOIN nodes n ON n.id = f.id
                    WHERE nodes_fts MATCH ?
                    ORDER BY rank LIMIT 5
                    """,
                    (fts_terms,),
                ).fetchall():
                    anchors.append(r)
                    anchor_meta[str(r["id"])] = {"matched_by": "fts5"}

        # 3. Semantic embedding fallback when lexical returns 0 anchors
        if not anchors and semantic_fallback:
            for r, sim in self._semantic_anchors(q_clean, min_sim=min_sim):
                anchors.append(r)
                anchor_meta[str(r["id"])] = {"matched_by": "semantic", "similarity": sim}

        if not anchors:
            return {"query": q_clean, "anchors": [], "by_type": {}, "total_connected": 0}

        visited: dict[str, int] = {str(r["id"]): 0 for r in anchors}
        frontier = set(visited.keys())

        for depth in range(1, max(1, min(hops, 3)) + 1):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            rows = self.conn.execute(
                f"SELECT src_id, dst_id FROM edges WHERE src_id IN ({placeholders}) OR dst_id IN ({placeholders})",
                (*frontier, *frontier),
            ).fetchall()
            next_frontier: set[str] = set()
            for r in rows:
                for cand in (str(r["src_id"]), str(r["dst_id"])):
                    if cand not in visited:
                        visited[cand] = depth
                        next_frontier.add(cand)
            frontier = next_frontier

        all_ids = list(visited.keys())
        placeholders = ",".join("?" for _ in all_ids)
        node_rows = self.conn.execute(f"SELECT * FROM nodes WHERE id IN ({placeholders})", all_ids).fetchall()

        by_type: dict[str, list[dict[str, object]]] = {}
        for r in node_rows:
            nid = str(r["id"])
            entry = {
                "id": nid,
                "title": str(r["title"]),
                "summary": str(r["summary"]),
                "source": str(r["source"]),
                "timestamp": str(r["timestamp"]),
                "ref_path": str(r["ref_path"]),
                "hop": visited[nid],
            }
            by_type.setdefault(str(r["node_type"]), []).append(entry)

        for ntype, items in by_type.items():
            items.sort(key=lambda x: (int(x["hop"]), str(x["timestamp"]) == "", str(x["timestamp"])), reverse=False)
            by_type[ntype] = items[:limit]

        return {
            "query": q_clean,
            "anchors": [
                {
                    "id": str(r["id"]),
                    "node_type": str(r["node_type"]),
                    "title": str(r["title"]),
                    **anchor_meta.get(str(r["id"]), {}),
                }
                for r in anchors
            ],
            "by_type": by_type,
            "total_connected": len(visited),
        }

    def stats(self) -> dict[str, object]:
        by_type = {
            str(r["node_type"]): int(r["c"])
            for r in self.conn.execute("SELECT node_type, COUNT(*) AS c FROM nodes GROUP BY node_type ORDER BY c DESC")
        }
        by_rel = {
            str(r["relation"]): int(r["c"])
            for r in self.conn.execute("SELECT relation, COUNT(*) AS c FROM edges GROUP BY relation ORDER BY c DESC")
        }
        return {
            "db_path": str(self.db_path),
            "nodes": sum(by_type.values()),
            "edges": sum(by_rel.values()),
            "nodes_by_type": by_type,
            "edges_by_relation": by_rel,
        }
