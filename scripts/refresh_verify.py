#!/usr/bin/env python3
"""Check figures and quotes against the real text of a web page.

Why this exists: WebFetch returns a model's summary of a page, and a summary can
contain figures that are not on the page. A /refresh-fix run cited "LCP from
3.78 s to 1.72 s" on a web.dev page that only says "improved LCP by 55%", because
the summary supplied the seconds. This script fetches the page itself (browser
headers, scripts and styles removed) and prints the actual text around each
search term, or NOT FOUND.

Usage:
  python3 scripts/refresh_verify.py --url URL TERM [TERM ...] [--url URL2 TERM ...] [--context 200]

Each TERM is searched case-insensitively as plain text ("3.78", "Vodafone",
"75th percentile"). Use it to look things up ("Vodafone", "LCP") and to check
figures before they go into the copy. A figure may be used only when it is FOUND
on the page it is attributed to; otherwise use the wording the page really has
(for example "55%"), or a [TODO · VERIFY] placeholder.
Standard library only.
"""
import html
import re
import subprocess
import sys

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def page_text(url):
    r = subprocess.run(["curl", "-sL", "--compressed", "--max-time", "30", "-A", UA,
                        "-H", "Accept: text/html,*/*;q=0.8", "-H", "Accept-Language: en-US,en;q=0.9",
                        "-w", "\n@@HTTP@@%{http_code}", url], capture_output=True)
    body, _, code = r.stdout.rpartition(b"\n@@HTTP@@")
    status = code.decode(errors="replace").strip()
    s = body.decode("utf-8", errors="replace")
    s = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace(" ", " ")
    return status, re.sub(r"\s+", " ", s).strip()


def main():
    a = sys.argv[1:]
    ctx = 200
    if "--context" in a:
        i = a.index("--context")
        ctx = int(a[i + 1])
        del a[i:i + 2]
    groups, cur = [], None
    for x in a:
        if x == "--url":
            cur = None
        elif cur is None:
            cur = {"url": x, "terms": []}
            groups.append(cur)
        else:
            cur["terms"].append(x)
    if not groups or not any(g["terms"] for g in groups):
        print("Usage: refresh_verify.py --url URL TERM [TERM ...] [--url URL2 TERM ...] [--context 200]")
        sys.exit(1)
    missing = 0
    for g in groups:
        status, text = page_text(g["url"])
        print(f"PAGE {g['url']} (HTTP {status}, {len(text)} characters of text)")
        if not status.startswith("2") or len(text) < 800:
            print("  CAN'T VERIFY: the page text is missing or too short (blocked, or rendered by JavaScript). "
                  "Treat every figure from this page as unverified: use a [TODO · VERIFY] placeholder.")
            missing += len(g["terms"])
            continue
        low = text.lower()
        for term in g["terms"]:
            hits = [m.start() for m in re.finditer(re.escape(term.lower()), low)]
            if not hits:
                print(f"  NOT FOUND: {term}")
                missing += 1
                continue
            print(f"  FOUND ({len(hits)}x): {term}")
            for pos in hits[:2]:
                snippet = text[max(0, pos - ctx // 2): pos + len(term) + ctx]
                print(f"    ...{snippet}...")
    if missing:
        print(f"\n{missing} term(s) not verified. Do not put them in the copy as sourced facts.")


if __name__ == "__main__":
    main()
