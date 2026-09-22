"""Notion API transport (urllib, stdlib only) plus an in-memory fake.

The transport converts between the internal block model (see markdown.py)
and Notion API block objects. Pagination, retries on 429, and archiving
are handled here so the engine stays transport-agnostic.

FakeNotionTransport implements the same interface against an in-memory
page tree and is what the test suite uses — no credentials required.
"""

import json
import os
import time
import urllib.request
import urllib.error


class TransportError(Exception):
    """Raised for Notion API failures after retries."""


class NotFound(TransportError):
    """The requested page or block no longer exists (404)."""


# ---------------------------------------------------------------------------
# internal block model -> Notion API objects
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "paragraph": "paragraph",
    "heading_1": "heading_1",
    "heading_2": "heading_2",
    "heading_3": "heading_3",
    "bulleted_list_item": "bulleted_list_item",
    "numbered_list_item": "numbered_list_item",
    "to_do": "to_do",
    "code": "code",
    "quote": "quote",
    "divider": "divider",
    "table": "table",
    "callout": "callout",
}


def _rich_to_notion(segs):
    out = []
    for s in segs:
        rt = {"type": "text", "text": {"content": s["text"]},
              "annotations": {
                  "bold": bool(s.get("bold")),
                  "italic": bool(s.get("italic")),
                  "strikethrough": bool(s.get("strike")),
                  "underline": False,
                  "code": bool(s.get("code")),
                  "color": "default",
              }}
        if s.get("href"):
            rt["text"]["link"] = {"url": s["href"]}
        out.append(rt)
    if not out:
        out.append({"type": "text", "text": {"content": ""},
                    "annotations": {"bold": False, "italic": False,
                                    "strikethrough": False, "underline": False,
                                    "code": False, "color": "default"}})
    return out


def _notion_to_rich(rich):
    segs = []
    for r in rich or []:
        if r.get("type") != "text":
            continue
        ann = r.get("annotations", {}) or {}
        text = (r.get("text") or {}).get("content", "")
        link = (r.get("text") or {}).get("link")
        segs.append({
            "text": text,
            "bold": bool(ann.get("bold")),
            "italic": bool(ann.get("italic")),
            "strike": bool(ann.get("strikethrough")),
            "code": bool(ann.get("code")),
            "href": (link or {}).get("url"),
        })
    from .markdown import _merge_segments
    return _merge_segments(segs) if segs else [
        {"text": "", "bold": False, "italic": False, "strike": False,
         "code": False, "href": None}]


def blocks_to_notion(blocks):
    """Internal block model -> Notion API block dicts (children nested)."""
    out = []
    for b in blocks:
        t = b.get("type")
        if t == "frontmatter":
            out.append({
                "type": "code",
                "code": {"rich_text": _rich_to_notion(
                    [{"text": "---notion-sync:frontmatter---\n"
                              + b.get("text", "")
                              + "\n---notion-sync:frontmatter---",
                      "bold": False, "italic": False, "strike": False,
                      "code": False, "href": None}]),
                    "language": "plain text"},
            })
            continue
        ntype = _TYPE_MAP.get(t)
        if ntype is None:
            # unknown: degrade to paragraph
            out.append({"type": "paragraph",
                        "paragraph": {"rich_text": _rich_to_notion(
                            b.get("rich", []))}})
            continue
        payload = {"type": ntype}
        if ntype == "divider":
            payload["divider"] = {}
        elif ntype == "code":
            payload["code"] = {
                "rich_text": _rich_to_notion(b.get("rich", [])),
                "language": b.get("language") or "plain text",
            }
        elif ntype == "to_do":
            payload["to_do"] = {
                "rich_text": _rich_to_notion(b.get("rich", [])),
                "checked": bool(b.get("checked")),
            }
        elif ntype == "table":
            width = max((len(r) for r in b.get("rows", [])), default=1)
            payload["table"] = {
                "table_width": width,
                "has_column_header": bool(b.get("has_column_header")),
                "has_row_header": False,
            }
            # API format: notion_to_blocks expects table_row objects here,
            # which is also what the live transport appends as children.
            payload["_table_rows"] = [
                {"type": "table_row",
                 "table_row": {"cells": [_rich_to_notion(cell)
                                        for cell in row]}}
                for row in b.get("rows", [])
            ]
        else:
            payload[ntype] = {"rich_text": _rich_to_notion(b.get("rich", []))}
        children = b.get("children", [])
        if children and ntype != "table":
            payload["children"] = blocks_to_notion(children)
        out.append(payload)
    return out


def notion_to_blocks(api_blocks):
    """Notion API block dicts -> internal block model."""
    out = []
    for nb in api_blocks or []:
        ntype = nb.get("type")
        if ntype == "table":
            rows = []
            for row in nb.get("_table_rows", []):
                cells = row.get("table_row", {}).get("cells", [])
                rows.append([_notion_to_rich(c) for c in cells])
            out.append({"type": "table", "rows": rows,
                        "has_column_header": bool(
                            nb.get("table", {}).get("has_column_header"))})
            continue
        inv = {v: k for k, v in _TYPE_MAP.items()}
        t = inv.get(ntype, "paragraph")
        data = nb.get(ntype, {}) if isinstance(nb.get(ntype), dict) else {}
        rich = _notion_to_rich(data.get("rich_text", []))
        blk = {"type": t, "rich": rich}
        if t == "code":
            lang = data.get("language", "plain text")
            text = "".join(s["text"] for s in rich)
            sentinel = "---notion-sync:frontmatter---"
            if text.startswith(sentinel) and text.rstrip().endswith(sentinel):
                inner = text[len(sentinel):-len(sentinel)].strip("\n")
                out.append({"type": "frontmatter", "text": inner})
                continue
            blk["language"] = "" if lang == "plain text" else lang
        if t == "to_do":
            blk["checked"] = bool(data.get("checked"))
        if nb.get("has_children"):
            blk["children"] = notion_to_blocks(nb.get("_children", []))
        elif nb.get("_children"):
            blk["children"] = notion_to_blocks(nb.get("_children"))
        elif nb.get("children"):
            # blocks_to_notion nests children under "children"
            blk["children"] = notion_to_blocks(nb.get("children"))
        out.append(blk)
    return out


# ---------------------------------------------------------------------------
# live HTTP transport
# ---------------------------------------------------------------------------

class NotionTransport:
    """Thin wrapper around the Notion REST API (urllib, no dependencies)."""

    def __init__(self, api_key, api_base="https://api.notion.com",
                 api_version="2022-06-28", timeout=30, max_retries=4):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.api_version = api_version
        self.timeout = timeout
        self.max_retries = max_retries

    # -- low level ------------------------------------------------------
    def _request(self, method, path, body=None):
        url = self.api_base + path
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", "Bearer " + self.api_key)
            req.add_header("Notion-Version", self.api_version)
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise NotFound(f"not found: {method} {path}")
                if e.code == 429 and attempt < self.max_retries:
                    wait = min(2 ** attempt, 16)
                    try:
                        ra = e.headers.get("Retry-After")
                        if ra:
                            wait = min(float(ra), 30)
                    except Exception:
                        pass
                    time.sleep(wait)
                    continue
                if e.code in (500, 502, 503) and attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 16))
                    continue
                raise TransportError(
                    f"Notion API {e.code} on {method} {path}: "
                    f"{e.read().decode('utf-8', 'replace')[:300]}")
            except urllib.error.URLError as e:
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 16))
                    continue
                raise TransportError(f"network error on {method} {path}: {e}")
        raise TransportError(f"exhausted retries on {method} {path}")

    def _paginate(self, method, path, body, key):
        items, cursor = [], None
        while True:
            b = dict(body or {})
            if cursor:
                b["start_cursor"] = cursor
            resp = self._request(method, path, b)
            items.extend(resp.get(key, []))
            if not resp.get("has_more"):
                return items
            cursor = resp.get("next_cursor")

    # -- pages ----------------------------------------------------------
    def get_page(self, page_id):
        """Return page object; raises NotFound when trashed/missing."""
        return self._request("GET", f"/v1/pages/{page_id}")

    def page_title(self, page):
        try:
            props = page.get("properties", {})
            title = props.get("title", {})
            if title.get("type") == "title":
                return "".join(t.get("plain_text", "")
                               for t in title.get("title", []))
        except Exception:
            pass
        return ""

    def create_page(self, parent_id, title):
        resp = self._request("POST", "/v1/pages", {
            "parent": {"page_id": parent_id},
            "properties": {"title": [{"text": {"content": title}}]},
        })
        return resp["id"]

    def archive_page(self, page_id):
        self._request("PATCH", f"/v1/pages/{page_id}", {"archived": True})

    def list_child_pages(self, parent_id):
        """Child pages of a parent (title + id + archived)."""
        blocks = self._paginate(
            "GET", f"/v1/blocks/{parent_id}/children", None, "results")
        out = []
        for b in blocks:
            if b.get("type") == "child_page":
                out.append({"id": b["id"], "title": b["child_page"]["title"],
                            "archived": bool(b.get("archived"))})
        return out

    # -- blocks ---------------------------------------------------------
    def get_blocks(self, page_id):
        """All blocks of a page, with nested children attached as _children."""
        return self._load_children(page_id)

    def _load_children(self, block_id):
        blocks = self._paginate(
            "GET", f"/v1/blocks/{block_id}/children", None, "results")
        for b in blocks:
            if b.get("has_children"):
                if b.get("type") == "table":
                    rows = self._paginate(
                        "GET", f"/v1/blocks/{b['id']}/children", None,
                        "results")
                    b["_table_rows"] = [r for r in rows
                                        if r.get("type") == "table_row"]
                else:
                    b["_children"] = self._load_children(b["id"])
        return blocks

    def replace_blocks(self, page_id, blocks):
        """Delete all non-child_page blocks, then append the new tree.

        Full-page replacement: block IDs change, so per-block comments or
        history on the old blocks are not preserved; child pages are kept
        (deleting a child_page block would trash the subpage). When the
        canonical content is unchanged this is a no-op — no API calls.
        """
        from . import markdown as md
        existing = self._paginate(
            "GET", f"/v1/blocks/{page_id}/children", None, "results")
        try:
            if md.canonical(notion_to_blocks(existing)) == md.canonical(blocks):
                return
        except Exception:
            pass  # on any comparison failure, fall through to replacement
        for b in existing:
            if b.get("type") == "child_page":
                continue  # deleting a child_page trashes the subpage
            self._request("DELETE", f"/v1/blocks/{b['id']}")
        self.append_blocks(page_id, blocks)

    def append_blocks(self, page_id, blocks):
        payload = blocks_to_notion(blocks)
        # table rows must be appended as children of their table block.
        # created[k] corresponds to chunk[k], so wire by position — this
        # handles multiple tables in one batch correctly.
        top = []
        table_rows = []  # (index in top, row blocks)
        for nb in payload:
            rows = nb.pop("_table_rows", None)
            if rows is not None:
                table_rows.append((len(top), rows))
            top.append(nb)
        for i in range(0, max(len(top), 1), 100):
            chunk = top[i:i + 100]
            if not chunk:
                continue
            resp = self._request(
                "PATCH", f"/v1/blocks/{page_id}/children",
                {"children": chunk})
            created = resp.get("results", [])
            for idx, rows in table_rows:
                if i <= idx < i + len(chunk) and rows:
                    created_block = created[idx - i]
                    if created_block.get("type") == "table":
                        for j in range(0, len(rows), 100):
                            self._request(
                                "PATCH",
                                f"/v1/blocks/{created_block['id']}/children",
                                {"children": rows[j:j + 100]})


# ---------------------------------------------------------------------------
# in-memory fake (tests, no credentials)
# ---------------------------------------------------------------------------

class FakeNotionTransport:
    """In-memory Notion stand-in with the same interface as NotionTransport.

    `persist_path` optionally saves the page tree to a JSON file after every
    mutation, so separate CLI processes can share one fake (used by the
    end-to-end CLI tests).
    """

    def __init__(self, persist_path=None):
        self.pages = {}          # id -> {"title", "archived", "blocks"}
        self.children = {}       # parent_id -> [child page ids]
        self._next = 0
        self.fail_on = None      # method name to fail with TransportError,
                                 # or (method, n) to fail on the nth call
        self.calls = {}          # method name -> call count
        self.replaced = 0        # replace_blocks calls that actually replaced
        self._persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            with open(persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.pages = data.get("pages", {})
            self.children = data.get("children", {})
            self._next = data.get("next", 0)

    def _save(self):
        if not self._persist_path:
            return
        tmp = self._persist_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"pages": self.pages, "children": self.children,
                       "next": self._next}, f)
        os.replace(tmp, self._persist_path)

    def _maybe_fail(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1
        if self.fail_on == name:
            raise TransportError(f"injected failure in {name}")
        if (isinstance(self.fail_on, tuple) and self.fail_on[0] == name
                and self.calls[name] == self.fail_on[1]):
            raise TransportError(
                f"injected failure in {name} (call {self.calls[name]})")

    def _new_id(self):
        self._next += 1
        return f"fake-page-{self._next:04d}"

    # -- pages ----------------------------------------------------------
    def get_page(self, page_id):
        self._maybe_fail("get_page")
        try:
            p = self.pages[page_id]
        except KeyError:
            raise NotFound(f"not found: {page_id}")
        return {"id": page_id, "archived": p["archived"],
                "properties": {"title": {"type": "title", "title": [
                    {"plain_text": p["title"]}]}}}

    def page_title(self, page):
        try:
            return page["properties"]["title"]["title"][0]["plain_text"]
        except Exception:
            return ""

    def create_page(self, parent_id, title):
        self._maybe_fail("create_page")
        pid = self._new_id()
        self.pages[pid] = {"title": title, "archived": False, "blocks": []}
        self.children.setdefault(parent_id, []).append(pid)
        self._save()
        return pid

    def archive_page(self, page_id):
        self._maybe_fail("archive_page")
        self.pages[page_id]["archived"] = True
        self._save()

    def list_child_pages(self, parent_id):
        self._maybe_fail("list_child_pages")
        out = []
        for pid in self.children.get(parent_id, []):
            p = self.pages[pid]
            out.append({"id": pid, "title": p["title"],
                        "archived": p["archived"]})
        return out

    # -- blocks ---------------------------------------------------------
    def get_blocks(self, page_id):
        self._maybe_fail("get_blocks")
        try:
            page = self.pages[page_id]
        except KeyError:
            raise NotFound(f"not found: {page_id}")
        import copy
        return copy.deepcopy(page["blocks"])

    def replace_blocks(self, page_id, blocks):
        self._maybe_fail("replace_blocks")
        import copy
        from . import markdown as md
        # store Notion API format, mirroring what the live transport sends,
        # so notion_to_blocks() round-trips correctly in pull_remote().
        new_api = copy.deepcopy(blocks_to_notion(blocks))
        try:
            old_api = self.pages[page_id]["blocks"]
            if (md.canonical(notion_to_blocks(old_api))
                    == md.canonical(notion_to_blocks(new_api))):
                return  # no-op: canonically identical, like the live transport
        except Exception:
            pass
        self.pages[page_id]["blocks"] = new_api
        self.replaced += 1
        self._save()

    def append_blocks(self, page_id, blocks):
        self._maybe_fail("append_blocks")
        import copy
        self.pages[page_id]["blocks"].extend(
            copy.deepcopy(blocks_to_notion(blocks)))
        self._save()
