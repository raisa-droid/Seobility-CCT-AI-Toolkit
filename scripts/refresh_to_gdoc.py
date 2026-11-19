#!/usr/bin/env python3
"""Convert a /refresh markdown Doc (Analyze or Fix) into Google-Docs-ready HTML.

Usage: python3 scripts/refresh_to_gdoc.py doc.md doc.html

Wraps scripts/write_to_gdoc.py (same markdown subset, same styling, same #f1fa8c
placeholder highlight) without changing it, and adds one thing: new copy in the
Fix Doc. Everything between a line `<!-- new -->` and a line `<!-- /new -->` gets
a light green highlight (#d9ead3), so new sections stand apart from yellow
placeholders. Placeholders inside new copy keep their yellow.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import write_to_gdoc as base  # noqa: E402

NEW = "background-color:#d9ead3"
MARKER = re.compile(r"^\s*<!--\s*(/?)new\s*-->\s*$")


def body_of(html):
    return re.sub(r"^.*?<body[^>]*>\n?|\n?</body></html>\s*$", "", html, flags=re.S)


def convert(md):
    segments, buf, is_new = [], [], False
    for line in md.splitlines():
        m = MARKER.match(line)
        if m:
            segments.append((is_new, "\n".join(buf)))
            buf, is_new = [], not m.group(1)
            continue
        buf.append(line)
    segments.append((is_new, "\n".join(buf)))

    plain_inline = base.inline
    out = []
    for new, text in segments:
        if not text.strip():
            continue
        if new:
            base.inline = lambda t: f'<span style="{NEW}">' + plain_inline(t) + "</span>"
        try:
            out.append(body_of(base.convert(text)))
        finally:
            base.inline = plain_inline
    return ('<html><head><meta charset="utf-8"></head><body style="font-family:Arial">\n'
            + "\n".join(out) + "\n</body></html>")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 scripts/refresh_to_gdoc.py doc.md doc.html")
    with open(sys.argv[1], encoding="utf-8") as f:
        result = convert(f.read())
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(result)
    print(f"Wrote {sys.argv[2]} ({result.count(base.HIGHLIGHT)} placeholders, "
          f"{result.count(NEW)} highlighted new-copy blocks)")
