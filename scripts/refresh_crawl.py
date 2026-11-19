#!/usr/bin/env python3
"""Crawl a published Seobility blog post and save a snapshot for /refresh.

Usage:
  python3 scripts/refresh_crawl.py URL             # crawl + save snapshot
  python3 scripts/refresh_crawl.py URL --compare   # re-crawl, diff against saved snapshot

Targets the Seobility blog template: the article body is div.post-content inside
main#primary. The H1, author and dates sit in the hero above it. Inside the body,
the in-post TOC (div.toc-container), <script>, <style> and <noscript> are skipped.
In-body CTA boxes and "In this post" boxes are kept and marked boxed=true. Blocks
inside <details> accordions are marked collapsed=true.

Every block (heading, paragraph, list, table, image, blockquote) gets an ID
(P1, P2, ...) so findings can point at exact places. Each block keeps plain
text and markdown (bold, italics, links) so /refresh-fix can edit the exact
crawled copy.

Writes to .refresh-cache/<slug>/:
  snapshot.json  full structured snapshot (what -fix edits)
  snapshot.md    readable copy with block IDs (what Claude reads in -analyze)

Prints a compact JSON summary to stdout. With --compare, nothing is saved and
the output lists blocks added, removed or changed since the snapshot.
Standard library only.
"""
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, ".refresh-cache")

# Cloudflare on seobility.net returns 403 to curl's default headers.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "form", "button"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "source", "track", "wbr"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
TEXT_BLOCKS = HEADINGS | {"p", "blockquote", "figcaption", "summary"}
SKIP_CLASSES = {"toc-container"}


def fail(msg):
    print(json.dumps({"data_available": False, "error": msg}))
    sys.exit(1)


def slug_of(url):
    path = urllib.parse.urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or "index"


def norm_space(s):
    return re.sub(r"\s+", " ", s).strip()


def is_box(attrs, cls):
    """A styled container in the body: CTA box, "In this post" summary, callout."""
    style = attrs.get("style", "").lower()
    return ("border" in style or "background" in style
            or any(k in c for c in cls for k in ("cta", "box", "callout", "highlight")))


def classes(attrs):
    return set((attrs.get("class") or "").split())


class Inline:
    """Collects the inline content of one block as plain text and markdown."""

    def __init__(self):
        self.text = []
        self.md = []

    def add(self, text, md=None):
        self.text.append(text)
        self.md.append(text if md is None else md)

    def result(self):
        text = norm_space("".join(self.text))
        md = norm_space("".join(self.md))
        # Drop empty bold pairs left by stray tags, and pull edge spaces out of
        # bold so "** text **" doesn't render literally.
        md = re.sub(r"\*\*\s*\*\*", " ", md)
        md = re.sub(r"\*\*(\s*)([^*]+?)(\s*)\*\*", r"\1**\2**\3", md)
        return text, norm_space(md)


class PostParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.stack = []            # open tags: (tag, attrs)
        self.head = {"title": "", "meta": {}, "canonical": "", "ld_json": []}
        self.hero_h1 = None        # first <h1> on the page (outside the body)
        self.hero_dates = []       # "Last updated: ..." / "Published: ..." spans
        self._h1_buf = None
        self._date_buf = None
        self._title_buf = None
        self._ld_buf = None

        self.is_single_post = False
        self.in_main = False
        self.body_depth = None     # stack depth where div.post-content opened
        self.skip_depth = None     # stack depth of a skipped subtree
        self.boxed_depths = []     # styled divs inside the body (CTA / summary boxes)
        self.details_depth = 0

        self.blocks = []
        self.links = []
        self.cur = None            # current text block: dict + Inline
        self.link = None           # current <a>: dict
        self.list_stack = []       # open lists: {"ordered", "items", "cur": Inline|None}
        self.table = None          # {"rows": [[cell...]], "cell": Inline|None}

    # ── helpers ──────────────────────────────────────────────────────────────
    def in_body(self):
        return self.body_depth is not None and self.skip_depth is None

    def emit(self, block):
        block["id"] = f"P{len(self.blocks) + 1}"
        block["boxed"] = bool(self.boxed_depths)
        block["collapsed"] = self.details_depth > 0
        self.blocks.append(block)
        for link in block.pop("_links", []):
            link["block"] = block["id"]
            self.links.append(link)
        return block

    def sink(self):
        """The Inline collector that text should go to right now, if any."""
        if self.cur:
            return self.cur["inline"]
        if self.table and self.table["cell"] is not None:
            return self.table["cell"]
        if self.list_stack and self.list_stack[-1]["cur"] is not None:
            return self.list_stack[-1]["cur"]
        return None

    def pending_links(self):
        if self.cur:
            return self.cur["links"]
        if self.table is not None:
            return self.table["links"]
        if self.list_stack:
            return self.list_stack[0]["links"]
        return None

    def classify_link(self, href):
        absu = urllib.parse.urljoin(self.base_url, href)
        p = urllib.parse.urlparse(absu)
        if href.startswith("#"):
            kind = "fragment"
        elif p.scheme in ("mailto", "tel", "javascript"):
            kind = p.scheme
        elif p.netloc.lower().endswith("seobility.net"):
            kind = "internal"
        else:
            kind = "external"
        return absu, kind

    # ── parser callbacks ─────────────────────────────────────────────────────
    def handle_starttag(self, tag, attrs_list):
        attrs = {k: (v or "") for k, v in attrs_list}
        if tag not in VOID_TAGS:
            self.stack.append((tag, attrs))
        depth = len(self.stack)
        cls = classes(attrs)

        # Head
        if tag == "title" and self.body_depth is None:
            self._title_buf = []
        elif tag == "meta":
            key = attrs.get("name") or attrs.get("property")
            if key and key not in self.head["meta"]:
                self.head["meta"][key] = attrs.get("content", "")
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.head["canonical"] = attrs.get("href", "")
        elif tag == "script" and attrs.get("type") == "application/ld+json":
            self._ld_buf = []

        if tag == "body":
            self.is_single_post = "single-post" in cls
        if tag == "main" and attrs.get("id") == "primary":
            self.in_main = True
        if self.body_depth is None:
            if tag == "h1" and self.hero_h1 is None:
                self._h1_buf = []
            if tag == "span" and "single-date" in cls:
                self._date_buf = []
            if self.in_main and tag == "div" and "post-content" in cls:
                self.body_depth = depth
            return

        # Inside the body
        if self.skip_depth is not None:
            return
        if tag in SKIP_TAGS or cls & SKIP_CLASSES:
            if tag not in VOID_TAGS:
                self.skip_depth = depth
            return

        if tag == "div" and not self.cur and is_box(attrs, cls):
            self.boxed_depths.append(depth)
        if tag == "details":
            self.details_depth += 1

        if tag in ("ul", "ol"):
            if self.list_stack and self.list_stack[-1]["cur"] is not None:
                # Nested list: flush the parent item's text so far as its own line.
                parent = self.list_stack[-1]
                parent["items"].append((len(self.list_stack) - 1, parent["cur"]))
                parent["cur"] = None
            self.list_stack.append({"ordered": tag == "ol", "items": [], "cur": None,
                                    "links": [] if not self.list_stack else None})
            if len(self.list_stack) > 1:
                self.list_stack[-1]["items"] = self.list_stack[0]["items"]
            return
        if tag == "li" and self.list_stack:
            top = self.list_stack[-1]
            top["cur"] = Inline()
            top["cur"].ordered = top["ordered"]
            return
        if tag == "table":
            self.table = {"rows": [], "cell": None, "row": None, "links": []}
            return
        if self.table is not None:
            if tag == "tr":
                self.table["row"] = []
            elif tag in ("td", "th"):
                self.table["cell"] = Inline()
            return

        if tag in TEXT_BLOCKS and not self.cur and not self.list_stack:
            if tag == "summary":
                return  # the heading inside <summary> becomes the block
            self.cur = {"tag": tag, "inline": Inline(), "links": [], "depth": depth,
                        "anchor": attrs.get("id", "")}
            return

        sink = self.sink()
        if tag == "a":
            href = attrs.get("href", "")
            absu, kind = self.classify_link(href) if href else ("", "none")
            self.link = {"href": absu, "raw_href": href, "type": kind,
                         "rel": attrs.get("rel", ""), "target": attrs.get("target", ""),
                         "anchor": [], "depth": depth}
            if sink:
                sink.add("", "[")
        elif tag in ("strong", "b") and sink:
            sink.add("", "**")
        elif tag in ("em", "i") and sink:
            sink.add("", "*")
        elif tag == "br" and sink:
            sink.add(" ", " ")
        elif tag == "img":
            src = attrs.get("data-lazy-src") or attrs.get("src", "")
            if src.startswith("data:"):
                src = ""
            if sink:
                if attrs.get("alt"):
                    sink.add("", f"![{attrs.get('alt')}]")
            elif not self.cur:
                self.emit({"type": "image", "alt": attrs.get("alt", ""), "src": src,
                           "text": "", "md": f"![{attrs.get('alt', '')}]({src})"})

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        # Pop to the matching open tag (tolerates unclosed <p>, <li> etc.).
        idx = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                idx = i
                break
        if idx is None:
            return
        depth = idx + 1
        # Close anything implicitly ended by this tag first.
        while len(self.stack) > depth:
            self.handle_endtag(self.stack[-1][0])
        self.stack.pop()

        if tag == "title" and self._title_buf is not None:
            self.head["title"] = norm_space("".join(self._title_buf))
            self._title_buf = None
        if tag == "script" and self._ld_buf is not None:
            self.head["ld_json"].append("".join(self._ld_buf))
            self._ld_buf = None
        if tag == "h1" and self._h1_buf is not None:
            self.hero_h1 = norm_space("".join(self._h1_buf))
            self._h1_buf = None
        if tag == "span" and self._date_buf is not None:
            self.hero_dates.append(norm_space("".join(self._date_buf)))
            self._date_buf = None
        if tag == "main":
            self.in_main = False

        if self.body_depth is None:
            return
        if self.skip_depth is not None:
            if depth == self.skip_depth:
                self.skip_depth = None
            return
        if depth == self.body_depth:
            self.body_depth = -1   # body closed; stop collecting
            self.skip_depth = 0
            return
        if self.boxed_depths and self.boxed_depths[-1] == depth:
            self.boxed_depths.pop()
        if tag == "details":
            self.details_depth -= 1

        sink = self.sink()
        if tag == "a" and self.link:
            link = self.link
            self.link = None
            anchor = norm_space("".join(link.pop("anchor")))
            link.pop("depth")
            link["anchor_text"] = anchor
            if sink:
                sink.add("", f"]({link['href']})")
            pending = self.pending_links()
            if pending is not None:
                pending.append(link)
            else:
                link["block"] = None
                self.links.append(link)
            return
        if tag in ("strong", "b") and sink:
            sink.add("", "**")
            return
        if tag in ("em", "i") and sink:
            sink.add("", "*")
            return

        if self.cur and depth == self.cur["depth"]:
            cur, self.cur = self.cur, None
            text, md = cur["inline"].result()
            if not text and not md:
                return
            t = cur["tag"]
            block = {"text": text, "_links": cur["links"]}
            if t in HEADINGS:
                block.update(type="heading", level=int(t[1]), md=text, anchor=cur["anchor"])
            elif t == "blockquote":
                block.update(type="blockquote", md="> " + md)
            else:
                block.update(type="paragraph", md=md)
            self.emit(block)
            return

        if tag == "li" and self.list_stack and self.list_stack[-1]["cur"] is not None:
            top = self.list_stack[-1]
            top["items"].append((len(self.list_stack) - 1, top["cur"]))
            top["cur"] = None
            return
        if tag in ("ul", "ol") and self.list_stack:
            top = self.list_stack.pop()
            if self.list_stack:
                return
            items = []
            for level, inl in top["items"]:
                text, md = inl.result()
                if text or md:
                    items.append({"level": level, "ordered": inl.ordered, "text": text, "md": md})
            if items:
                lines = []
                counters = {}
                for it in items:
                    counters[it["level"]] = counters.get(it["level"], 0) + 1
                    for deeper in [k for k in counters if k > it["level"]]:
                        counters.pop(deeper)
                    bullet = f"{counters[it['level']]}. " if it["ordered"] else "- "
                    lines.append("  " * it["level"] + bullet + it["md"])
                self.emit({"type": "list", "ordered": top["ordered"], "items": items,
                           "text": " ".join(i["text"] for i in items), "md": "\n".join(lines),
                           "_links": top["links"]})
            return

        if self.table is not None:
            if tag in ("td", "th") and self.table["cell"] is not None:
                text, md = self.table["cell"].result()
                self.table["row"].append(md.replace("|", "/"))
                self.table["cell"] = None
            elif tag == "tr" and self.table["row"] is not None:
                if any(self.table["row"]):
                    self.table["rows"].append(self.table["row"])
                self.table["row"] = None
            elif tag == "table":
                rows = self.table["rows"]
                links = self.table["links"]
                self.table = None
                if rows:
                    width = max(len(r) for r in rows)
                    rows = [r + [""] * (width - len(r)) for r in rows]
                    md = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
                    md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
                    self.emit({"type": "table", "rows": rows, "md": "\n".join(md),
                               "text": " ".join(" ".join(r) for r in rows), "_links": links})

    def handle_data(self, data):
        if self._title_buf is not None:
            self._title_buf.append(data)
        if self._ld_buf is not None:
            self._ld_buf.append(data)
        if self._h1_buf is not None:
            self._h1_buf.append(data)
        if self._date_buf is not None:
            self._date_buf.append(data)
        if not self.in_body():
            return
        if self.link is not None:
            self.link["anchor"].append(data)
        sink = self.sink()
        if sink:
            sink.add(data)


# ── extraction ───────────────────────────────────────────────────────────────
def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            return r.status, r.geturl(), r.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        fail(f"HTTP {e.code} fetching {url}")
    except urllib.error.URLError as e:
        fail(f"Could not fetch {url}: {e.reason}")


def find_dates(parser):
    meta = parser.head["meta"]
    published = meta.get("article:published_time", "")
    modified = meta.get("article:modified_time", "")
    if not (published and modified):
        for raw in parser.head["ld_json"]:
            published = published or (re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw) or [None, ""])[1]
            modified = modified or (re.search(r'"dateModified"\s*:\s*"([^"]+)"', raw) or [None, ""])[1]
    return {
        "published": published[:10],
        "updated": modified[:10],
        "on_page": parser.hero_dates,   # what readers see, e.g. "Last updated: ..."
    }


def build_snapshot(url):
    status, final_url, page = fetch(url)
    parser = PostParser(final_url)
    parser.feed(page)
    parser.close()
    if not parser.is_single_post:
        fail("Not a single blog post (category, archive or index page).")
    if parser.body_depth is None:
        fail("Article container (main#primary div.post-content) not found. "
             "The page may not use the Seobility blog template.")
    blocks = parser.blocks
    if not blocks:
        fail("Article container found but no content blocks were extracted.")

    title = html.unescape(parser.head["title"])
    meta_desc = parser.head["meta"].get("description", "")
    h1_in_body = [b for b in blocks if b["type"] == "heading" and b["level"] == 1]
    outline = [{"id": b["id"], "level": b["level"], "text": b["text"]}
               for b in blocks if b["type"] == "heading"]
    words = sum(len(b["text"].split()) for b in blocks)
    content_links = [l for l in parser.links if l["type"] in ("internal", "external")]

    for b in blocks:
        b["hash"] = hashlib.sha1(b["text"].encode()).hexdigest()[:12]

    return {
        "url": url,
        "final_url": final_url,
        "http_status": status,
        "slug": slug_of(final_url),
        "crawled_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "h1": parser.hero_h1 or "",
        "h1_count": (1 if parser.hero_h1 else 0) + len(h1_in_body),
        "title": title,
        "title_length": len(title),
        "meta_description": meta_desc,
        "meta_description_length": len(meta_desc),
        "canonical": parser.head["canonical"],
        "dates": find_dates(parser),
        "stats": {
            "blocks": len(blocks),
            "words": words,
            "h2": sum(1 for o in outline if o["level"] == 2),
            "h3": sum(1 for o in outline if o["level"] == 3),
            "links_internal": sum(1 for l in content_links if l["type"] == "internal"),
            "links_external": sum(1 for l in content_links if l["type"] == "external"),
        },
        "outline": outline,
        "blocks": blocks,
        "links": parser.links,
    }


def render_md(snap):
    out = [
        f"# {snap['h1']}",
        "",
        f"- URL: {snap['final_url']}",
        f"- Title tag ({snap['title_length']} chars): {snap['title']}",
        f"- Meta description ({snap['meta_description_length']} chars): {snap['meta_description']}",
        f"- Published: {snap['dates']['published']} · Updated: {snap['dates']['updated']}",
        f"- Words: {snap['stats']['words']} · H1 count: {snap['h1_count']}",
        f"- Crawled: {snap['crawled_at']}",
        "",
        "Block IDs in [brackets]. {box} = inside a styled box (CTA, summary). "
        "{collapsed} = inside an accordion.",
        "",
        "---",
        "",
    ]
    for b in snap["blocks"]:
        tags = "".join([" {box}" if b["boxed"] else "", " {collapsed}" if b["collapsed"] else ""])
        if b["type"] == "heading":
            out.append(f"{'#' * b['level']} [{b['id']}]{tags} {b['text']}")
        elif b["type"] in ("list", "table"):
            out.append(f"[{b['id']}]{tags}")
            out.append(b["md"])
        else:
            out.append(f"[{b['id']}]{tags} {b['md']}")
        out.append("")
    out += ["---", "", "## Links", "", "Block · Type · Anchor · Href · Rel", ""]
    for l in snap["links"]:
        if l["type"] in ("internal", "external"):
            out.append(f"- {l['block']} · {l['type']} · {l['anchor_text'] or '(no anchor)'} · "
                       f"{l['href']}{' · ' + l['rel'] if l['rel'] else ''}")
    return "\n".join(out) + "\n"


def summary(snap, paths):
    return {
        "data_available": True,
        "url": snap["url"],
        "final_url": snap["final_url"],
        "slug": snap["slug"],
        "h1": snap["h1"],
        "h1_count": snap["h1_count"],
        "title": snap["title"],
        "title_length": snap["title_length"],
        "meta_description": snap["meta_description"],
        "meta_description_length": snap["meta_description_length"],
        "dates": snap["dates"],
        "stats": snap["stats"],
        **paths,
    }


def compare(old, new):
    """Match blocks by text hash; report what was removed, added or changed."""
    old_hashes = [b["hash"] for b in old["blocks"]]
    new_hashes = [b["hash"] for b in new["blocks"]]
    removed = [b for b in old["blocks"] if b["hash"] not in set(new_hashes)]
    added = [b for b in new["blocks"] if b["hash"] not in set(old_hashes)]
    meta_changes = {k: {"snapshot": old[k], "live": new[k]}
                    for k in ("h1", "title", "meta_description") if old[k] != new[k]}
    return {
        "data_available": True,
        "url": new["url"],
        "snapshot_crawled_at": old["crawled_at"],
        "live_updated": new["dates"]["updated"],
        "changed": bool(removed or added or meta_changes),
        "meta_changes": meta_changes,
        "blocks_removed": [{"id": b["id"], "text": b["text"][:200]} for b in removed],
        "blocks_added": [{"after_live_block": new["blocks"][max(0, int(b["id"][1:]) - 2)]["id"]
                          if int(b["id"][1:]) > 1 else None,
                          "text": b["text"][:200]} for b in added],
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) != 1:
        fail("Usage: refresh_crawl.py URL [--compare]")
    url = args[0].strip()
    if not re.match(r"https?://", url):
        url = "https://" + url
    if "/blog" not in urllib.parse.urlparse(url).path:
        fail("URL must contain /blog. Only Seobility blog posts are supported.")

    snap = build_snapshot(url)
    folder = os.path.join(CACHE, snap["slug"])
    snap_json = os.path.join(folder, "snapshot.json")

    if "--compare" in flags:
        if not os.path.exists(snap_json):
            fail(f"No saved snapshot at {os.path.relpath(snap_json, REPO)}. Run -analyze first.")
        with open(snap_json) as f:
            old = json.load(f)
        print(json.dumps(compare(old, snap), ensure_ascii=False, indent=2))
        return

    os.makedirs(folder, exist_ok=True)
    snap_md = os.path.join(folder, "snapshot.md")
    with open(snap_json, "w") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    with open(snap_md, "w") as f:
        f.write(render_md(snap))
    print(json.dumps(summary(snap, {
        "snapshot_json": os.path.relpath(snap_json, REPO),
        "snapshot_md": os.path.relpath(snap_md, REPO),
    }), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
