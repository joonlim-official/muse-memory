"""Loss-aware Markdown <-> Notion block conversion.

Block model (plain dicts, JSON-serializable):

    {"type": "paragraph", "rich": [seg, ...], "children": [...]}
    {"type": "heading_1" | "heading_2" | "heading_3", "rich": [...]}
    {"type": "bulleted_list_item" | "numbered_list_item", "rich": [...],
     "children": [...]}
    {"type": "to_do", "rich": [...], "checked": bool, "children": [...]}
    {"type": "code", "rich": [...], "language": str}
    {"type": "quote", "rich": [...], "children": [...]}
    {"type": "divider"}
    {"type": "table", "rows": [[ [seg...], ... ], ...],
     "has_column_header": bool}
    {"type": "frontmatter", "text": str}   # raw YAML between --- fences

Segment: {"text": str, "bold": bool, "italic": bool, "strike": bool,
          "code": bool, "href": str | None}

Design notes (documented in references/notion-sync.md):
- Comparison uses canonical(blocks): structural, not textual. List marker
  style (- vs *), heading spacing, blank-line runs, and table alignment
  are normalized away; indentation *inside code blocks*, nested-list
  structure, and rich-text annotations are preserved.
- Notion has only 3 heading levels: h4-h6 map to heading_3.
- Frontmatter round-trips through a fenced yaml code block carrying a
  sentinel line, so it survives as an ordinary Notion block.
"""

import json
import re

# ---------------------------------------------------------------------------
# inline rich-text parsing
# ---------------------------------------------------------------------------

_TOKEN = re.compile(
    r"(?P<code>`[^`\n]+`)"
    r"|(?P<link>\[[^\]\n]+\]\([^)\s\n]+\))"
    r"|(?P<bold>\*\*[^*\n]+\*\*|__[^_\n]+__)"
    r"|(?P<strike>~~[^~\n]+~~)"
    r"|(?P<italic>\*[^*\n]+\*|(?<![A-Za-z0-9])_[^_\n]+_(?![A-Za-z0-9]))"
)


def _seg(text, **kw):
    seg = {"text": text, "bold": False, "italic": False, "strike": False,
           "code": False, "href": None}
    seg.update(kw)
    return seg


def parse_inline(s):
    """Parse inline markdown into rich-text segments."""
    segs = []
    pos = 0
    for m in _TOKEN.finditer(s):
        if m.start() > pos:
            segs.append(_seg(s[pos:m.start()]))
        kind = m.lastgroup
        body = m.group(0)
        if kind == "code":
            segs.append(_seg(body[1:-1], code=True))
        elif kind == "link":
            text = body[1:body.index("]")]
            href = body[body.index("(") + 1:-1]
            segs.append(_seg(text, href=href))
        elif kind == "bold":
            segs.append(_seg(body[2:-2], bold=True))
        elif kind == "strike":
            segs.append(_seg(body[2:-2], strike=True))
        elif kind == "italic":
            inner = body[1:-1]
            segs.append(_seg(inner, italic=True))
        pos = m.end()
    if pos < len(s):
        segs.append(_seg(s[pos:]))
    if not segs:
        segs.append(_seg(""))
    return _merge_segments(segs)


def _merge_segments(segs):
    """Merge adjacent segments with identical annotations (comparison-stable)."""
    out = []
    for s in segs:
        if out and all(s[k] == out[-1][k] for k in ("bold", "italic", "strike", "code", "href")):
            out[-1]["text"] += s["text"]
        else:
            out.append(dict(s))
    return [s for s in out if s["text"] != "" or len(out) == 1]


def render_inline(segs):
    """Render rich-text segments back to inline markdown."""
    out = []
    for s in segs:
        t = s["text"]
        if s.get("code"):
            # code wins over other annotations in markdown
            out.append("`" + t.replace("`", "") + "`")
            continue
        if s.get("bold"):
            t = "**" + t + "**"
        if s.get("italic"):
            t = "*" + t + "*"
        if s.get("strike"):
            t = "~~" + t + "~~"
        href = s.get("href")
        if href:
            t = "[" + t + "](" + href + ")"
        out.append(t)
    return "".join(out)


# ---------------------------------------------------------------------------
# block parsing (markdown -> blocks)
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^(`{3,})(\w*)\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$")
_TASK = re.compile(r"^\[([ xX])\]\s+(.*)$")
_DIVIDER = re.compile(r"^\s*(\*{3,}|-{3,}|_{3,})\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")

FRONTMATTER_SENTINEL = "---notion-sync:frontmatter---"


def _is_table_sep(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c) for c in cells)


def _split_row(line):
    # split on unescaped pipes
    parts, cur, esc = [], [], False
    for ch in line.strip().strip("|"):
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def parse_markdown(text):
    """Parse markdown text into a list of blocks. Never raises on odd input."""
    lines = text.split("\n")
    blocks = []
    i, n = 0, len(lines)

    # frontmatter: leading --- ... --- fence
    if n and lines[0].strip() == "---":
        for j in range(1, min(n, 200)):
            if lines[j].strip() == "---":
                blocks.append({"type": "frontmatter",
                               "text": "\n".join(lines[1:j])})
                i = j + 1
                break

    para = []

    def flush_para():
        if para:
            blocks.append({"type": "paragraph",
                           "rich": parse_inline("\n".join(para))})
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        m = _FENCE.match(line)
        if m:
            flush_para()
            fence, lang = m.group(1), m.group(2)
            body = []
            i += 1
            while i < n and not lines[i].lstrip().startswith(fence):
                body.append(lines[i])
                i += 1
            i += 1  # consume closing fence (or EOF)
            if lang == "frontmatter" and body and body[0] == FRONTMATTER_SENTINEL \
                    and body[-1] == FRONTMATTER_SENTINEL:
                blocks.append({"type": "frontmatter",
                               "text": "\n".join(body[1:-1])})
            else:
                blocks.append({"type": "code", "language": lang,
                               "rich": [_seg("\n".join(body))]})
            continue

        m = _HEADING.match(stripped)
        if m:
            flush_para()
            level = min(len(m.group(1)), 3)  # Notion has 3 heading levels
            blocks.append({"type": f"heading_{level}",
                           "rich": parse_inline(m.group(2).strip())})
            i += 1
            continue

        if _DIVIDER.match(line) and not (i == 0 and stripped == "---"):
            flush_para()
            blocks.append({"type": "divider"})
            i += 1
            continue

        # table: header row + separator row
        if "|" in line and i + 1 < n and _is_table_sep(lines[i + 1]):
            flush_para()
            rows = [[parse_inline(c.strip()) for c in _split_row(line)]]
            i += 2
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append([parse_inline(c.strip())
                             for c in _split_row(lines[i])])
                i += 1
            width = max(len(r) for r in rows)
            rows = [r + [[_seg("")] for _ in range(width - len(r))] for r in rows]
            blocks.append({"type": "table", "rows": rows,
                           "has_column_header": True})
            continue

        m = _QUOTE.match(line)
        if m:
            flush_para()
            qlines = []
            while i < n:
                qm = _QUOTE.match(lines[i])
                if not qm:
                    break
                qlines.append(qm.group(1))
                i += 1
            blocks.append({"type": "quote",
                           "rich": parse_inline("\n".join(qlines))})
            continue

        m = _LIST.match(line)
        if m:
            flush_para()
            items, i = _parse_list(lines, i)
            blocks.extend(items)
            continue

        para.append(line.strip())
        i += 1

    flush_para()
    return blocks


def _parse_list(lines, i):
    """Parse consecutive list-item lines into nested blocks. Returns (blocks, i)."""
    raw = []
    n = len(lines)
    while i < n:
        m = _LIST.match(lines[i])
        if not m:
            break
        indent = len(m.group(1).replace("\t", "    "))
        marker = m.group(2)
        rest = m.group(3)
        task = _TASK.match(rest)
        if task:
            btype = "to_do"
            checked = task.group(1).lower() == "x"
            text = task.group(2)
        elif marker[0].isdigit():
            btype = "numbered_list_item"
            checked, text = False, rest
        else:
            btype = "bulleted_list_item"
            checked, text = False, rest
        raw.append((indent, btype, checked, text))
        i += 1

    # nest by relative indentation (stack algorithm: robust to 2/4-space styles)
    root, stack = [], []  # stack of (indent, block)
    for indent, btype, checked, text in raw:
        blk = {"type": btype, "rich": parse_inline(text), "children": []}
        if btype == "to_do":
            blk["checked"] = checked
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(blk)
        else:
            root.append(blk)
        stack.append((indent, blk))
    return root, i


# ---------------------------------------------------------------------------
# block rendering (blocks -> markdown)
# ---------------------------------------------------------------------------

def blocks_to_markdown(blocks):
    """Render blocks back to markdown. Deterministic: same blocks, same text."""
    out = []
    for b in blocks:
        _render_block(b, 0, out)
    text = "\n".join(out)
    # collapse 3+ blank runs to a double newline, strip leading/trailing blanks
    text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
    return text + "\n" if text else ""


def _render_block(b, level, out):
    t = b.get("type")
    rich = b.get("rich", [])
    if t == "frontmatter":
        # restore literal --- delimiters so the local file round-trips
        # byte-identical; the sentinel code-block form is only for Notion
        out.append("---")
        out.append(b.get("text", ""))
        out.append("---")
        out.append("")
    elif t in ("heading_1", "heading_2", "heading_3"):
        lvl = int(t[-1])
        out.append("#" * lvl + " " + render_inline(rich))
        out.append("")
    elif t == "paragraph":
        out.append(render_inline(rich))
        out.append("")
    elif t == "bulleted_list_item":
        _render_list_item("- ", b, level, out)
    elif t == "numbered_list_item":
        _render_list_item("1. ", b, level, out)
    elif t == "to_do":
        mark = "x" if b.get("checked") else " "
        _render_list_item(f"- [{mark}] ", b, level, out)
    elif t == "code":
        lang = b.get("language", "")
        out.append("```" + lang)
        out.append(render_inline(rich))
        out.append("```")
        out.append("")
    elif t == "quote":
        for ql in render_inline(rich).split("\n"):
            out.append("> " + ql if ql else ">")
        out.append("")
    elif t == "divider":
        out.append("---")
        out.append("")
    elif t == "table":
        rows = b.get("rows", [])
        if rows:
            width = max(len(r) for r in rows)
            md_rows = []
            for r in rows:
                cells = [render_inline(c).replace("|", "\\|") for c in r]
                cells += [""] * (width - len(cells))
                md_rows.append("| " + " | ".join(cells) + " |")
            out.append(md_rows[0])
            out.append("| " + " | ".join(["---"] * width) + " |")
            out.extend(md_rows[1:])
            out.append("")
    else:
        # unknown block types degrade to a paragraph of their text
        if rich:
            out.append(render_inline(rich))
            out.append("")
    for child in b.get("children", []):
        if t in ("bulleted_list_item", "numbered_list_item", "to_do"):
            continue  # already rendered nested by _render_list_item
        _render_block(child, level, out)


def _render_list_item(prefix, b, level, out):
    indent = "  " * level
    out.append(indent + prefix + render_inline(b.get("rich", [])))
    for child in b.get("children", []):
        ct = child.get("type")
        if ct in ("bulleted_list_item", "numbered_list_item", "to_do"):
            _render_block(child, level + 1, out)
        else:
            # non-list child under a list item: render at deeper indent
            sub = []
            _render_block(child, 0, sub)
            for sl in sub:
                out.append(indent + "  " + sl if sl.strip() else sl)


# ---------------------------------------------------------------------------
# canonical form for three-way comparison
# ---------------------------------------------------------------------------

def _canon_block(b):
    t = b.get("type")
    node = {"type": t}
    if t == "frontmatter":
        node["text"] = b.get("text", "").strip()
    elif t == "code":
        node["language"] = b.get("language", "")
        node["text"] = render_inline(b.get("rich", []))  # exact, incl. indent
    elif t == "table":
        node["rows"] = [[render_inline(c) for c in r]
                        for r in b.get("rows", [])]
    elif t == "to_do":
        node["checked"] = bool(b.get("checked"))
        node["text"] = render_inline(b.get("rich", []))
    elif t == "divider":
        pass
    else:
        node["text"] = render_inline(b.get("rich", []))
    children = b.get("children", [])
    if children:
        node["children"] = [_canon_block(c) for c in children]
    return node


def canonical(blocks):
    """Structural canonical form. Formatting-only differences compare equal;
    indentation inside code, nesting, and annotations are preserved."""
    return json.dumps([_canon_block(b) for b in blocks],
                      sort_keys=True, ensure_ascii=False)


def canonical_text(markdown_text):
    """Parse then canonicalize — the comparison entry point."""
    return canonical(parse_markdown(markdown_text))
