#!/usr/bin/env python3
"""Fetch and strip competitor pages for /refresh-analyze Step 5.

Usage:
  python3 scripts/refresh_fetch.py --slug POST_SLUG URL [URL ...]

For each page: keeps the outline, article text, formats used (tables, ordered
and bulleted lists, step headings) and FAQs. Nav, header, footer, sidebars,
comments, cookie banners, share bars, TOCs and related-post blocks are dropped.
FAQs come from a visible FAQ section or <details> questions ("page") and from
FAQPage schema ("schema"); schema FAQs often just repeat the article headings.

Works on any site (no template): noise is removed by tag, role and class/id,
then the article root is found by walking down from <body> while one child
still holds at least 80% of the remaining text.

Fallback: if a page can't be fetched (blocked, error) or yields under 300 words,
DataForSEO content parsing is used instead, via the DataForSEO credentials in .env (webhook or login)
($0.00015 per page, tested 2026-10-01). It flattens lists into lines, so for
those pages list counts are null (unknown) and only tables are counted.

Writes .refresh-cache/<slug>/competitors/<n>_<domain>.md (full readable text),
<n>_<domain>.digest.md (a short digest: outline, one lead sentence per section,
sentences with numbers, formats, FAQ questions; about 2k tokens) and fetch.json.
/refresh-analyze reads the digests; the full text stays on disk for grep when a
topic needs checking. Prints a short summary to stdout (details are in the files).
Standard library only.
"""
import concurrent.futures
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refresh_api  # noqa: E402
from html.parser import HTMLParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, ".refresh-cache")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
MIN_WORDS = 300

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "source", "track", "wbr"}
# Tags whose open instance is closed by a new tag of the same kind.
SELF_CLOSING_SIBLINGS = {"p", "li", "tr", "td", "th", "dt", "dd", "option"}
DROP_TAGS = {"script", "style", "noscript", "svg", "iframe", "form", "button", "nav",
             "aside", "select", "template", "dialog", "canvas", "video", "audio", "picture"}
DROP_ROLES = {"navigation", "complementary", "banner", "contentinfo", "search", "dialog"}
NOISE = re.compile(
    r"(^|[-_ ])(nav|navbar|navigation|menu|footer|sidebar|side-bar|comments?|cookie|consent|"
    r"gdpr|share|sharing|social|related|newsletter|subscribe|subscription|breadcrumbs?|popup|"
    r"modal|advert|ads|promo|toc|table-of-contents|ez-toc|author-box|author-bio|"
    r"post-navigation|pagination|skip-link|sr-only|visually-hidden)([-_ ]|$)", re.I)
KEEP_ALWAYS = {"html", "body", "main", "article"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
TEXT_BLOCKS = {"p", "blockquote", "figcaption", "dt", "dd", "summary", "pre"}
FAQ_HEADING = re.compile(r"\b(faqs?|frequently asked|common questions|questions and answers|q\s*&\s*a)\b", re.I)
STEP_HEADING = re.compile(r"^\s*(step\s*\d+|\d+\s*[.):]\s)", re.I)


def norm_space(s):
    return re.sub(r"\s+", " ", s).strip()


# ── DOM ──────────────────────────────────────────────────────────────────────
class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.parent = parent

    def text(self):
        out = []
        stack = [self]
        while stack:
            n = stack.pop()
            if isinstance(n, str):
                out.append(n)
            else:
                stack.extend(reversed(n.children))
        return norm_space(" ".join(out))

    def iter(self):
        stack = [self]
        while stack:
            n = stack.pop()
            if isinstance(n, Node):
                yield n
                stack.extend(reversed(n.children))

    def has_ancestor(self, tags):
        p = self.parent
        while p is not None:
            if p.tag in tags:
                return True
            p = p.parent
        return False


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root
        self.meta = {}
        self.title = ""
        self.ld_json = []
        self._in_title = False
        self._ld = None

    def handle_starttag(self, tag, attrs_list):
        attrs = {k: (v or "") for k, v in attrs_list}
        if tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            if key and key.lower() not in self.meta:
                self.meta[key.lower()] = attrs.get("content", "")
        if tag == "title":
            self._in_title = True
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self._ld = []
        if tag in SELF_CLOSING_SIBLINGS and self.cur.tag == tag:
            self.cur = self.cur.parent
        if tag == "p" and self.cur.tag == "p":
            self.cur = self.cur.parent
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs_list):
        self.handle_starttag(tag, attrs_list)
        if tag not in VOID and self.cur.tag == tag:
            self.cur = self.cur.parent

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._ld is not None:
            self.ld_json.append("".join(self._ld))
            self._ld = None
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._ld is not None:
            self._ld.append(data)
        self.cur.children.append(data)


# ── extraction ───────────────────────────────────────────────────────────────
def is_noise(n):
    if n.tag in KEEP_ALWAYS:
        return False
    if n.tag in DROP_TAGS:
        return True
    if n.tag in ("header", "footer") and not n.has_ancestor({"article"}):
        return True
    if (n.attrs.get("role") or "").lower() in DROP_ROLES:
        return True
    if n.attrs.get("aria-hidden") == "true" or "hidden" in n.attrs:
        return True
    ident = f"{n.attrs.get('class', '')} {n.attrs.get('id', '')}"
    return bool(ident.strip()) and bool(NOISE.search(ident))


def strip_noise(root):
    for n in list(root.iter()):
        n.children = [c for c in n.children if isinstance(c, str) or not is_noise(c)]


def content_len(n):
    """Text in content-bearing tags, ignoring link text (menus, link lists)."""
    total = 0
    for d in n.iter():
        if d.tag in TEXT_BLOCKS or d.tag in ("li", "td", "th") or d.tag in HEADINGS:
            if d.has_ancestor(TEXT_BLOCKS | {"li", "td", "th"} | HEADINGS) and d.parent is not n:
                continue
            t = len(d.text())
            links = sum(len(a.text()) for a in d.iter() if a.tag == "a")
            total += max(0, t - links)
    return total


def find_root(body):
    node = body
    while True:
        kids = [c for c in node.children if isinstance(c, Node)]
        if not kids:
            return node
        total = content_len(node)
        if total == 0:
            return node
        best = max(kids, key=content_len)
        if content_len(best) >= 0.8 * total:
            node = best
        else:
            return node


def inline_md(n):
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
            return
        if x.tag == "br":
            out.append(" ")
            return
        if x.tag in ("strong", "b"):
            out.append("**")
            for c in x.children:
                walk(c)
            out.append("**")
            return
        for c in x.children:
            walk(c)

    walk(n)
    md = norm_space("".join(out))
    md = re.sub(r"\*\*\s*\*\*", " ", md)
    return norm_space(re.sub(r"\*\*(\s*)([^*]+?)(\s*)\*\*", r"\1**\2**\3", md))


def extract_blocks(root):
    """Headings, paragraphs, lists, tables, in document order."""
    blocks = []

    def list_items(lst, level, out):
        for li in lst.children:
            if not isinstance(li, Node) or li.tag != "li":
                continue
            nested = [c for c in li.children if isinstance(c, Node) and c.tag in ("ul", "ol")]
            own = Node("li")
            own.children = [c for c in li.children if not (isinstance(c, Node) and c.tag in ("ul", "ol"))]
            text = inline_md(own)
            if text:
                out.append({"level": level, "ordered": lst.tag == "ol", "text": text})
            for sub in nested:
                list_items(sub, level + 1, out)

    def walk(n):
        if isinstance(n, str):
            return
        t = n.tag
        if t in HEADINGS:
            text = n.text()
            if text:
                blocks.append({"type": "heading", "level": int(t[1]), "text": text})
            return
        if t in ("ul", "ol"):
            items = []
            list_items(n, 0, items)
            if items:
                blocks.append({"type": "list", "ordered": t == "ol", "items": items})
            return
        if t == "table":
            rows = []
            for tr in n.iter():
                if tr.tag == "tr":
                    cells = [c.text().replace("|", "/") for c in tr.children
                             if isinstance(c, Node) and c.tag in ("td", "th")]
                    if any(cells):
                        rows.append(cells)
            if rows:
                blocks.append({"type": "table", "rows": rows})
            return
        if t == "details":
            summ = next((c for c in n.children if isinstance(c, Node) and c.tag == "summary"), None)
            if summ is not None:
                blocks.append({"type": "summary", "text": summ.text()})
            for c in n.children:
                if c is not summ:
                    walk(c)
            return
        if t in TEXT_BLOCKS:
            text = inline_md(n)
            if text:
                blocks.append({"type": "paragraph", "text": text, "tag": t})
            return
        # Loose text directly inside a container (sites that skip <p>).
        loose = norm_space(" ".join(c for c in n.children if isinstance(c, str)))
        has_blocks = any(isinstance(c, Node) and (c.tag in TEXT_BLOCKS or c.tag in HEADINGS
                         or c.tag in ("ul", "ol", "table", "div", "section")) for c in n.children)
        if len(loose) > 40 and not has_blocks:
            blocks.append({"type": "paragraph", "text": inline_md(n), "tag": t})
            return
        for c in n.children:
            walk(c)

    walk(root)
    return blocks


def faq_from_ld(ld_json):
    out = []

    def visit(o):
        if isinstance(o, list):
            for x in o:
                visit(x)
        elif isinstance(o, dict):
            types = o.get("@type")
            types = types if isinstance(types, list) else [types]
            if "Question" in types:
                ans = o.get("acceptedAnswer") or {}
                if isinstance(ans, list):
                    ans = ans[0] if ans else {}
                a = html.unescape(re.sub(r"<[^>]+>", " ", str(ans.get("text", ""))))
                out.append({"q": norm_space(html.unescape(str(o.get("name", "")))),
                            "a": norm_space(a), "source": "schema"})
            for v in o.values():
                if isinstance(v, (list, dict)):
                    visit(v)

    for raw in ld_json:
        try:
            visit(json.loads(raw))
        except (ValueError, TypeError):
            continue
    return out


def faq_from_blocks(blocks):
    """Questions under an FAQ heading, plus <details> summaries phrased as questions."""
    out = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b["type"] == "heading" and FAQ_HEADING.search(b["text"]):
            level = b["level"]
            i += 1
            q, a = None, []
            while i < len(blocks):
                c = blocks[i]
                if c["type"] == "heading" and c["level"] <= level:
                    break
                is_q = ((c["type"] in ("heading", "summary"))
                        or (c["type"] == "paragraph" and c["text"].rstrip("*").endswith("?") and len(c["text"]) < 200))
                if is_q:
                    if q:
                        out.append({"q": q, "a": " ".join(a), "source": "page"})
                    q, a = c["text"].strip("* "), []
                elif q and c["type"] == "paragraph":
                    a.append(c["text"])
                elif q and c["type"] == "list":
                    a.append(" ".join(it["text"] for it in c["items"]))
                i += 1
            if q:
                out.append({"q": q, "a": " ".join(a), "source": "page"})
            continue
        if b["type"] == "summary" and b["text"].endswith("?"):
            ans = []
            j = i + 1
            while j < len(blocks) and blocks[j]["type"] in ("paragraph", "list"):
                ans.append(blocks[j].get("text") or " ".join(it["text"] for it in blocks[j]["items"]))
                j += 1
            out.append({"q": b["text"], "a": " ".join(ans), "source": "page"})
        i += 1
    return out


def dedupe_faq(items):
    """Merge by question; a question both on the page and in schema is "page+schema"."""
    out = {}
    for it in items:
        key = re.sub(r"[^a-z0-9]", "", it["q"].lower())
        if not it["q"]:
            continue
        if key in out:
            if out[key]["source"] != it["source"]:
                out[key]["source"] = "page+schema"
            if not out[key]["a"]:
                out[key]["a"] = it["a"]
        else:
            out[key] = dict(it)
    return list(out.values())


def formats_of(blocks):
    lists = [b for b in blocks if b["type"] == "list" and len(b["items"]) >= 3]
    return {
        "tables": sum(1 for b in blocks if b["type"] == "table"),
        "ordered_lists": sum(1 for b in lists if b["ordered"]),
        "bullet_lists": sum(1 for b in lists if not b["ordered"]),
        "step_headings": sum(1 for b in blocks if b["type"] == "heading" and STEP_HEADING.match(b["text"])),
    }


def dates_of(meta, ld_json):
    pub = meta.get("article:published_time", "")
    mod = meta.get("article:modified_time", "") or meta.get("og:updated_time", "")
    for raw in ld_json:
        pub = pub or (re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw) or [None, ""])[1]
        mod = mod or (re.search(r'"dateModified"\s*:\s*"([^"]+)"', raw) or [None, ""])[1]
    return {"published": pub[:10] or None, "updated": mod[:10] or None}


def word_count(blocks):
    n = 0
    for b in blocks:
        if b["type"] == "list":
            n += sum(len(it["text"].split()) for it in b["items"])
        elif b["type"] == "table":
            n += sum(len(" ".join(r).split()) for r in b["rows"])
        else:
            n += len(b["text"].split())
    return n


# ── fetch paths ──────────────────────────────────────────────────────────────
def fetch_direct(url):
    """Fetch with curl: macOS system Python's TLS is too old for some sites."""
    cmd = ["curl", "-sL", "--compressed", "--max-time", "30", "-o", "-",
           "-w", "\n%{http_code}\t%{url_effective}\t%{content_type}"]
    for k, v in HEADERS.items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd + [url], capture_output=True)
    if r.returncode != 0:
        raise OSError(f"curl error {r.returncode}")
    body, _, meta = r.stdout.rpartition(b"\n")
    status, final_url, ctype = (meta.decode(errors="replace").split("\t") + ["", "", ""])[:3]
    final_url = re.sub(r"^(https://[^/]+):443(?=/|$)|^(http://[^/]+):80(?=/|$)",
                       lambda m: m.group(1) or m.group(2), final_url)
    if not status.isdigit() or int(status) >= 400:
        raise OSError(f"HTTP {status}")
    if "html" not in ctype:
        raise ValueError(f"not an HTML page ({ctype or 'unknown type'})")
    m = re.search(r"charset=([\w-]+)", ctype)
    return int(status), final_url, body.decode(m.group(1) if m else "utf-8", errors="replace")


def parse_direct(url):
    status, final_url, page = fetch_direct(url)
    tb = TreeBuilder()
    tb.feed(page)
    tb.close()
    # Some pages have more than one <body> (e.g. an empty one from injected markup).
    bodies = [n for n in tb.root.iter() if n.tag == "body"] or [tb.root]
    body = max(bodies, key=content_len)
    h1_node = next((n for n in body.iter() if n.tag == "h1"), None)
    h1 = h1_node.text() if h1_node is not None else ""
    strip_noise(body)
    root = find_root(body)
    blocks = extract_blocks(root)
    if h1 and not any(b["type"] == "heading" and b["level"] == 1 for b in blocks):
        blocks.insert(0, {"type": "heading", "level": 1, "text": h1})
    faq = dedupe_faq(faq_from_ld(tb.ld_json) + faq_from_blocks(blocks))
    return {
        "method": "direct",
        "http_status": status,
        "final_url": final_url,
        "title": norm_space(tb.title),
        "h1": h1,
        "meta_description": tb.meta.get("description", ""),
        "dates": dates_of(tb.meta, tb.ld_json),
        "blocks": blocks,
        "formats": formats_of(blocks),
        "faq": faq,
    }


def parse_dataforseo(url):
    data = refresh_api.dfs_post("https://api.dataforseo.com/v3/on_page/content_parsing/live", [{"url": url}])
    task = (data.get("tasks") or [{}])[0]
    if task.get("status_code") != 20000:
        raise RuntimeError(f"content parsing failed: {task.get('status_message')}")
    item = ((task.get("result") or [{}])[0].get("items") or [{}])[0]
    content = item.get("page_content") or {}
    blocks = []
    for topic in content.get("main_topic") or []:
        if topic.get("h_title"):
            blocks.append({"type": "heading", "level": topic.get("level") or 2, "text": norm_space(topic["h_title"])})
        for pc in topic.get("primary_content") or []:
            if pc.get("text"):
                blocks.append({"type": "paragraph", "text": norm_space(pc["text"]), "tag": "p"})
        for tbl in topic.get("table_content") or []:
            rows = [[norm_space(c.get("text", "")) for c in (row.get("row_cells") or row.get("cells") or [])]
                    for row in (tbl.get("rows") or tbl.get("table_rows") or [])]
            if rows:
                blocks.append({"type": "table", "rows": rows})
    # Repeated title blocks are common in parsed output; keep the first of each.
    seen, deduped = set(), []
    for b in blocks:
        key = (b["type"], b.get("text"))
        if b["type"] == "heading" and key in seen:
            continue
        seen.add(key)
        deduped.append(b)
    blocks = deduped
    h1 = next((b["text"] for b in blocks if b["type"] == "heading" and b["level"] == 1), "")
    fmts = formats_of(blocks)
    fmts.update(ordered_lists=None, bullet_lists=None)
    return {
        "method": "dataforseo",
        "http_status": item.get("status_code"),
        "final_url": url,
        "title": h1,
        "h1": h1,
        "meta_description": "",
        "dates": {"published": None, "updated": None},
        "blocks": blocks,
        "formats": fmts,
        "faq": dedupe_faq(faq_from_blocks(blocks)),
    }


def process(url):
    direct_error = None
    try:
        page = parse_direct(url)
        if word_count(page["blocks"]) >= MIN_WORDS:
            return page
        direct_error = f"only {word_count(page['blocks'])} words extracted"
    except (ValueError, OSError) as e:
        direct_error = str(e)
        if "not an HTML page" in direct_error:
            raise
    try:
        page = parse_dataforseo(url)
    except Exception as e:
        raise RuntimeError(f"direct fetch: {direct_error}; fallback: {e}")
    if word_count(page["blocks"]) < MIN_WORDS:
        raise RuntimeError(f"direct fetch: {direct_error}; fallback: only "
                           f"{word_count(page['blocks'])} words extracted")
    page["direct_error"] = direct_error
    return page


# ── output ───────────────────────────────────────────────────────────────────
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
FACT = re.compile(r"\d[\d,.]*\s?(%|percent|ms|milliseconds?|seconds?|secs?|kb|mb|gb|times)\b|\b(19|20)\d\d\b", re.I)
DIGEST_MAX = 9000


def plain(text):
    return norm_space(MD_LINK.sub(r"\1", text).replace("**", ""))


def first_sentence(text, cap=200):
    t = plain(text)
    m = re.search(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])", t)
    t = t[:m.start()] if m else t
    return t if len(t) <= cap else t[:cap - 1].rstrip() + "…"


def build_digest(page, with_h3_leads=True):
    blocks = page["blocks"]
    out = [f"# {page['h1'] or page['title']}", "",
           f"- URL: {page['final_url']}",
           f"- Words: {page['word_count']} · Formats: {json.dumps(page['formats'])} · FAQs: {len(page['faq'])}",
           f"- Published: {page['dates']['published']} · Updated: {page['dates']['updated']}", "",
           "## Outline with lead sentences", ""]
    want_lead, shown_table = False, False
    facts, heading = [], ""
    for b in blocks:
        t = b["type"]
        if t == "heading":
            indent = "  " * max(0, b["level"] - 2)
            out.append(f"{indent}H{b['level']} {b['text']}")
            heading, want_lead, shown_table = b["text"], (b["level"] <= 2 or with_h3_leads), False
        elif t == "paragraph":
            if want_lead:
                out.append(f"{'  ' * 2}> {first_sentence(b['text'])}")
                want_lead = False
            if len(facts) < 14:
                for sent in re.split(r"(?<=[.!?])\s+", plain(b["text"])):
                    if FACT.search(sent) and 40 <= len(sent) <= 260:
                        facts.append((heading, sent))
                        break
        elif t == "list":
            items = [it["text"] for it in b["items"]]
            if len(items) >= 3:
                kind = "numbered" if b.get("ordered") else "bullets"
                out.append(f"  [{kind}, {len(items)} items] " + " | ".join(plain(x)[:55] for x in items[:5]))
            if len(facts) < 14:
                for it in items:
                    if FACT.search(it) and 30 <= len(plain(it)) <= 260:
                        facts.append((heading, plain(it)))
                        break
        elif t == "table" and not shown_table:
            out.append(f"  [table] columns: {', '.join(plain(c)[:30] for c in b['rows'][0][:6])}")
            shown_table = True
    if page["faq"]:
        out += ["", "## FAQ questions", ""] + [f"- {f['q']} ({f['source']})" for f in page["faq"][:10]]
    if facts:
        out += ["", "## Sentences with numbers or dates", ""]
        out += [f"- [{h[:40]}] {x}" for h, x in facts[:14]]
    text = "\n".join(out) + "\n"
    if len(text) > DIGEST_MAX and with_h3_leads:
        return build_digest(page, with_h3_leads=False)
    return text[:DIGEST_MAX]


def render_md(url, page):
    out = [f"# {page['h1'] or page['title']}", "",
           f"- URL: {page['final_url']}",
           f"- Title tag: {page['title']}",
           f"- Fetched via: {page['method']}",
           f"- Published: {page['dates']['published']} · Updated: {page['dates']['updated']}",
           f"- Words: {page['word_count']}",
           f"- Formats: {json.dumps(page['formats'])}",
           f"- FAQs: {len(page['faq'])}", "", "---", ""]
    for b in page["blocks"]:
        if b["type"] == "heading":
            out.append("#" * min(b["level"], 6) + " " + b["text"])
        elif b["type"] == "list":
            n = {}
            for it in b["items"]:
                n[it["level"]] = n.get(it["level"], 0) + 1
                for k in [k for k in n if k > it["level"]]:
                    n.pop(k)
                bullet = f"{n[it['level']]}. " if it["ordered"] else "- "
                out.append("  " * it["level"] + bullet + it["text"])
        elif b["type"] == "table":
            rows = b["rows"]
            w = max(len(r) for r in rows)
            rows = [r + [""] * (w - len(r)) for r in rows]
            out.append("| " + " | ".join(rows[0]) + " |")
            out.append("|" + "---|" * w)
            out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        elif b["type"] == "summary":
            out.append(f"**{b['text']}**")
        else:
            out.append(b["text"])
        out.append("")
    if page["faq"]:
        out += ["---", "", "## Extracted FAQs", ""]
        for f in page["faq"]:
            out += [f"**Q: {f['q']}** ({f['source']})", f"A: {f['a']}", ""]
    return "\n".join(out) + "\n"


def main():
    args = sys.argv[1:]
    if "--slug" not in args or len(args) < 3:
        print(json.dumps({"data_available": False,
                          "error": "Usage: refresh_fetch.py --slug POST_SLUG URL [URL ...]"}))
        sys.exit(1)
    i = args.index("--slug")
    slug = args[i + 1]
    urls = args[:i] + args[i + 2:]
    folder = os.path.join(CACHE, slug, "competitors")
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        os.remove(os.path.join(folder, f))

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {u: pool.submit(process, u) for u in urls}

    pages, failed = [], []
    for n, url in enumerate(urls, 1):
        try:
            page = futures[url].result()
        except Exception as e:
            failed.append({"url": url, "error": str(e)})
            continue
        page["word_count"] = word_count(page["blocks"])
        domain = re.sub(r"^www\.", "", urllib.parse.urlparse(page["final_url"]).netloc)
        path = os.path.join(folder, f"{n}_{re.sub(r'[^a-z0-9.-]', '_', domain.lower())}.md")
        with open(path, "w") as f:
            f.write(render_md(url, page))
        digest_path = path[:-3] + ".digest.md"
        with open(digest_path, "w") as f:
            f.write(build_digest(page))
        pages.append({
            "url": url,
            "final_url": page["final_url"],
            "method": page["method"],
            **({"direct_error": page["direct_error"]} if page.get("direct_error") else {}),
            "title": page["title"],
            "h1": page["h1"],
            "dates": page["dates"],
            "word_count": page["word_count"],
            "formats": page["formats"],
            "faq_count": len(page["faq"]),
            "faq_sources": sorted({f["source"] for f in page["faq"]}),
            "text_file": os.path.relpath(path, REPO),
            "digest_file": os.path.relpath(digest_path, REPO),
        })

    result = {"data_available": bool(pages), "pages": pages, "failed": failed}
    with open(os.path.join(CACHE, slug, "fetch.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    # Short stdout: the details are in fetch.json and the digest files.
    lines = [f"Fetched {len(pages)} of {len(urls)} pages."]
    for p in pages:
        fb = f" (fallback: {p['direct_error']})" if p.get("direct_error") else ""
        lines.append(f"- {p['digest_file']} | {p['word_count']} words | {p['method']}{fb} | {p['final_url']}")
    for fl in failed:
        lines.append(f"- FAILED {fl['url']}: {fl['error']}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
