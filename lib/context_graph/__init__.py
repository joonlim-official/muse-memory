"""Holistic Personal Context Graph DB (SQLite3 + FTS5) for muse-memory.

Connects geo/timeline data, curated agent memory, voice notes (Plaud), email,
chat, purchase/order data, photo context, and calendar/context events into a
single queryable topic graph with zero third-party dependencies.
"""

from .graph import ContextGraph, DEFAULT_DB_NAME, EDGE_RELATIONS, NODE_TYPES

__all__ = ["ContextGraph", "DEFAULT_DB_NAME", "NODE_TYPES", "EDGE_RELATIONS"]
