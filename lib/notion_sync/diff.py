"""Incremental block diff: current Notion blocks vs desired blocks.

Compares one level of the block tree at a time with difflib's
SequenceMatcher over canonical per-block signatures, then recurses into
the children of blocks that were updated in place. Blank paragraphs are
paired in order as alignment anchors first, so content is never slid
across blank separators.

diff_blocks(current, desired_payloads, parent_id) returns an ordered op
list; each op is a dict:

    {"op": "update", "id": <block_id>,
     "payload": <API block dict without id/children>,
     "orig": <deepcopy of the current API block>}
    {"op": "delete", "id": <block_id>,
     "orig": <deepcopy of the current API block>,
     "parent": <parent block or page id>, "after": "start" | <block_id>}
    {"op": "insert", "parent": <parent block or page id>,
     "after": "start" | <block_id> | PREV,
     "payloads": [<API block dicts, children nested>]}

Semantics for the engine:
- "update": same Notion type at the aligned position, content differs
  -> PATCH in place; the block id (and any per-block Notion metadata)
  is preserved. A block is only rewritten when its own content
  changed — a pure child change recurses without touching the parent.
- "delete": block archived; children go with it.
- "insert": appended under "parent". "after" is a block id that is
  guaranteed to still exist when the op applies (it survived every
  earlier op), "start" to prepend, or PREV to chain after the block
  created by the immediately preceding insert op.
- Blocks that are canonically equal at a level produce no ops — not even
  for their children, since the signature covers the whole subtree.

Reorder semantics: alignment is positional, so a reorder updates
same-type blocks in place (ids preserved) rather than archiving and
re-creating them — the Notion API has no move operation, and positional
updates keep every block id stable. Content that has no same-type
counterpart at its aligned position is archived and re-inserted.

Only blocks whose Notion type the sync can represent should be passed
in as "current" (see transport.MANAGED_BLOCK_TYPES); anything else
(child pages, images, embeds, ...) is left out of the diff and is never
touched by a push.
"""

import copy
import difflib

from . import markdown as md
from . import transport as tp


class _PrevType:
    pass


PREV = _PrevType()
"""Sentinel for insert chaining: anchor after the previously created block."""


def _sig(api_block):
    """Canonical signature of one API-format block (subtree included)."""
    return md.canonical(tp.notion_to_blocks([api_block]))


def _is_empty_para(api_block):
    """True for an empty paragraph in API shape (blank-line separator)."""
    if api_block.get("type") != "paragraph":
        return False
    rt = (api_block.get("paragraph") or {}).get("rich_text") or []
    return all(not seg.get("text", {}).get("content") for seg in rt)


def _sigs(blocks):
    """Per-block signatures for one diff level.

    Blank paragraphs all share one signature: they are fungible
    padding, so difflib can match any blank with any blank when a
    blank line is added or removed. Cross-blank content sliding is
    still prevented by the positional blank anchors in
    _segmented_opcodes (a pure reorder keeps every blank at its
    index, forcing positional pairing); occurrence-indexing blanks
    instead makes every blank add/remove cascade churn.
    """
    return [_sig(b) for b in blocks]


def _segmented_opcodes(current, desired):
    """difflib opcodes with blank separators pre-aligned as anchors.

    A blank paragraph anchors the alignment only when it sits at the
    same index on both sides: positional, never forced. Pairing blanks
    by order (k-th to k-th) misaligns every later segment when a blank
    line itself is added or removed, cascading delete+insert churn
    across unrelated blocks. With positional anchors, a blank add/remove
    simply leaves that region unanchored and difflib aligns the content
    by signature; reorder stability is preserved because a pure reorder
    keeps every blank at its index.
    Yields (tag, i1, i2, j1, j2) with global indices, one segment at a
    time.
    """
    cur_blank_set = set(i for i, b in enumerate(current)
                        if _is_empty_para(b))
    anchors = [(-1, -1)]
    for j, p in enumerate(desired):
        if j < len(current) and j in cur_blank_set and _is_empty_para(p):
            anchors.append((j, j))
    anchors.append((len(current), len(desired)))
    for (ai, aj), (bi, bj) in zip(anchors, anchors[1:]):
        a_sigs = _sigs(current[ai + 1:bi])
        b_sigs = _sigs(desired[aj + 1:bj])
        sm = difflib.SequenceMatcher(None, a_sigs, b_sigs, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            yield tag, ai + 1 + i1, ai + 1 + i2, aj + 1 + j1, aj + 1 + j2
        # the anchor blank itself: equal by construction, no op
        if bi < len(current) and bj < len(desired):
            yield "equal", bi, bi + 1, bj, bj + 1


def _shallow_sig(api_block):
    """Canonical signature of a block's own content, children excluded."""
    b = copy.deepcopy(api_block)
    for key in ("_children", "_table_rows", "children"):
        if key in b:
            b[key] = []
    return _sig(b)


def _kids(api_block):
    if api_block.get("type") == "table":
        return list(api_block.get("_table_rows") or [])
    return list(api_block.get("_children") or [])


def _payload_kids(payload):
    if payload.get("type") == "table":
        return list(payload.get("_table_rows") or [])
    return list(payload.get("children") or [])


def strip_payload(payload):
    """API block dict reduced to what update_block PATCH accepts."""
    p = copy.deepcopy(payload)
    p.pop("id", None)
    p.pop("children", None)
    p.pop("_children", None)
    p.pop("_table_rows", None)
    return p


def update_payload_for(api_block):
    """Build an update_block payload that restores an API block's content."""
    t = api_block.get("type")
    data = api_block.get(t)
    payload = {"type": t}
    if isinstance(data, dict):
        payload[t] = copy.deepcopy(data)
    else:
        payload[t] = {}
    return payload


def diff_blocks(current, desired_payloads, parent_id):
    """Diff one page (or one parent block) level. Returns the op list."""
    ops = []
    _diff_level(current, desired_payloads, parent_id, ops)
    return ops


def _diff_level(current, desired, parent_id, ops):
    deleted = [False] * len(current)

    def anchor_before(i):
        """Nearest surviving block id before position i, else "start"."""
        for k in range(i - 1, -1, -1):
            if not deleted[k]:
                return current[k]["id"]
        return "start"

    for tag, i1, i2, j1, j2 in _segmented_opcodes(current, desired):
        if tag == "equal":
            continue
        if tag == "delete":
            for k in range(i1, i2):
                deleted[k] = True
                ops.append({"op": "delete", "id": current[k]["id"],
                            "orig": copy.deepcopy(current[k]),
                            "parent": parent_id,
                            "after": anchor_before(k)})
            continue
        if tag == "insert":
            ops.append({"op": "insert", "parent": parent_id,
                        "after": anchor_before(i1),
                        "payloads": [copy.deepcopy(p)
                                     for p in desired[j1:j2]]})
            continue
        # replace: pair up positionally; same type -> in-place update,
        # different type -> delete + insert (ids cannot be reused).
        prev = anchor_before(i1)
        na, nb = i2 - i1, j2 - j1
        for n in range(min(na, nb)):
            a_blk, b_pay = current[i1 + n], desired[j1 + n]
            if a_blk.get("type") == b_pay.get("type"):
                ck, dk = _kids(a_blk), _payload_kids(b_pay)
                kids_differ = ([_sig(c) for c in ck]
                               != [_sig(d) for d in dk])
                # update the block itself only when its own content
                # changed; a pure child change recurses without
                # rewriting the parent.
                if _shallow_sig(a_blk) != _shallow_sig(b_pay):
                    ops.append({"op": "update", "id": a_blk["id"],
                                "payload": strip_payload(b_pay),
                                "orig": copy.deepcopy(a_blk)})
                prev = a_blk["id"]
                if kids_differ:
                    _diff_level(ck, dk, a_blk["id"], ops)
            else:
                deleted[i1 + n] = True
                ops.append({"op": "delete", "id": a_blk["id"],
                            "orig": copy.deepcopy(a_blk),
                            "parent": parent_id, "after": prev})
                ops.append({"op": "insert", "parent": parent_id,
                            "after": prev,
                            "payloads": [copy.deepcopy(b_pay)]})
                prev = PREV
        for k in range(i1 + min(na, nb), i2):
            deleted[k] = True
            ops.append({"op": "delete", "id": current[k]["id"],
                        "orig": copy.deepcopy(current[k]),
                        "parent": parent_id,
                        "after": anchor_before(k)})
        extra = desired[j1 + min(na, nb):j2]
        if extra:
            ops.append({"op": "insert", "parent": parent_id,
                        "after": prev,
                        "payloads": [copy.deepcopy(p) for p in extra]})
    return ops
