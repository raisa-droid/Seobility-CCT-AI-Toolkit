#!/usr/bin/env python3
"""Convert a /write markdown draft into Google-Docs-ready HTML.

Usage: python3 scripts/write_to_gdoc.py draft.md draft.html

Handles the markdown subset /write produces: # / ## / ### headings, paragraphs,
bold, [text](url) links, bare URLs, --- dividers, tables, and bulleted/numbered
lists (nested by 2-space indent). [TODO · TYPE: message] placeholders get the
#f1fa8c highlight. Styles are inline because Google Docs ignores <style> blocks
on import.
"""
import html
import re
import sys

HIGHLIGHT = "background-color:#f1fa8c"
P = '<p style="line-height:1.15;margin:0;padding-top:0pt;padding-bottom:10pt">'
LI = '<li style="line-height:1.15;margin:0;padding-bottom:4pt">'
TD = '<td style="line-height:1.15;padding:4pt">'
TH = '<th style="background-color:#eeeeee;line-height:1.15;padding:4pt">'

LIST_ITEM = re.compile(r"^(\s*)(- |\d+\. )(.*)$")
BLOCK_START = re.compile(r"(#{1,3} |\||---\s*$|\s*(- |\d+\. ))")


def inline(text):
    text = html.escape(text, quote=False)
    # Protect placeholders first so their brackets aren't read as links.
    text = re.sub(r"\[(TODO · [^\]]*)\]", lambda m: "\x00" + m.group(1) + "\x01", text)
    text = re.sub(r"\[([^\]\[]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    # Bare URLs, without trailing punctuation.
    text = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<;,)]+[^\s<;,.:)])', r'<a href="\1">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text.replace("\x00", f'<span style="{HIGHLIGHT}">[').replace("\x01", "]</span>")


def render_list(items):
    """items: list of (level, ordered, text). Children nest inside the parent <li>."""
    out, stack = [], []  # stack of open list tags
    for level, ordered, text in items:
        level = min(level, len(stack))  # never skip a level
        tag = "ol" if ordered else "ul"
        while len(stack) > level + 1:
            out.append(f"</li></{stack.pop()}>")
        if len(stack) == level + 1 and stack[-1] != tag:
            # Bullets switching to numbers (or back) at the same level start a new list.
            out.append(f"</li></{stack.pop()}>")
        if len(stack) == level + 1:
            out.append("</li>")
        else:
            stack.append(tag)
            out.append(f"<{tag}>")
        out.append(LI + inline(text))
    while stack:
        out.append(f"</li></{stack.pop()}>")
    return "".join(out)


def convert(md):
    out = ['<html><head><meta charset="utf-8"></head><body style="font-family:Arial">']
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.strip() == "---":
            # The empty paragraph stops Docs merging the divider into the next heading.
            out.append("<hr>\n" + P + "</p>")
            i += 1
            continue
        heading = re.match(r"(#{1,3}) (.*)", line)
        if heading:
            n = len(heading.group(1))
            out.append(f"<h{n}>{inline(heading.group(2))}</h{n}>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            table = '<table border="1" style="border-collapse:collapse"><tr>'
            table += "".join(TH + inline(c) + "</th>" for c in rows[0]) + "</tr>"
            for row in rows[2:]:  # rows[1] is the |---| separator
                table += "<tr>" + "".join(TD + inline(c) + "</td>" for c in row) + "</tr>"
            out.append(table + "</table>")
            continue
        if LIST_ITEM.match(line):
            items = []
            while i < len(lines) and LIST_ITEM.match(lines[i]):
                indent, marker, text = LIST_ITEM.match(lines[i]).groups()
                items.append((len(indent) // 2, marker != "- ", text))
                i += 1
            out.append(render_list(items))
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not BLOCK_START.match(lines[i]):
            para.append(inline(lines[i]))
            i += 1
        out.append(P + "<br>".join(para) + "</p>")
    out.append("</body></html>")
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python3 scripts/write_to_gdoc.py draft.md draft.html")
    with open(sys.argv[1], encoding="utf-8") as f:
        result = convert(f.read())
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(result)
    print(f"Wrote {sys.argv[2]} ({result.count(HIGHLIGHT)} highlighted placeholders)")
