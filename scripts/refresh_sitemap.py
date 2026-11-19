#!/usr/bin/env python3
"""Internal link candidates for /refresh-analyze, from the Sitemap Cache sheet.

The Sitemap Cache (Google Drive) lists every Seobility page: url, h1, lastmod,
about 440 rows. Claude used to read the whole sheet into the chat (about 25k
tokens, including raw base64). This script keeps a local copy and returns only
the pages that fit the post, so Claude reads about 1k tokens.

Usage:
  python3 scripts/refresh_sitemap.py status
      fresh / stale / missing, and the age of the local copy (stale after 7 days)
  python3 scripts/refresh_sitemap.py ingest FILE
      FILE is what the Drive connector's download_file_content saved: a JSON
      wrapper with base64 xlsx in "content", or a raw .xlsx. Writes
      .refresh-cache/sitemap.json (shared by all posts).
  python3 scripts/refresh_sitemap.py query SLUG [--terms "a, b, c"] [--top 25]
      Scores blog and wiki pages against the post (its headings, the primary
      keyword, --terms such as the entity names), drops the post itself and
      pages it already links, and prints the best matches.

Output: ALL remaining blog posts (about 85 in total, one short line each, best
matches first) so Claude can judge them by meaning, plus the best-scoring wiki
entries (297 in total, shortlist only). Scoring: shared word stems between the
post's headings/keywords and the candidate's H1 and URL slug, weighted by how
rare the stem is across the sitemap; terms of three or more words must match as phrases
(at least 60% of their stems). Standard library only.
"""
import base64
import html
import io
import json
import math
import os
import re
import sys
import time
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, ".refresh-cache")
SITEMAP = os.path.join(CACHE, "sitemap.json")
TTL_DAYS = 7
STOP = set("""a an and are as at be but by can do does for from how i if in into is it its more my no not of
on or our so than that the their then there these they this to up us was we what when where which who why will
with you your seobility seo website websites site sites page pages guide tips best way ways need needs""".split())


def fail(msg):
    print(json.dumps({"data_available": False, "error": msg}))
    sys.exit(1)


def stem(w):
    w = w.lower()
    if len(w) > 4:
        w = re.sub(r"(ies|ing|ed|es|s)$", "", w)
    if len(w) > 6:
        w = re.sub(r"er$", "", w)
    if len(w) > 4:
        w = re.sub(r"e$", "", w)
    return w


def stems(text):
    return [stem(w) for w in re.findall(r"[A-Za-z][A-Za-z0-9]+", text) if w.lower() not in STOP and len(w) > 2]


def norm_url(u):
    u = u.lower().split("#")[0].split("?")[0].rstrip("/")
    return re.sub(r"^https?://(www\.)?", "", u)


def kind_of(url):
    if "/blog/" in url:
        return "blog"
    if "/wiki/" in url:
        return "wiki"
    return "other"


# ── ingest ───────────────────────────────────────────────────────────────────
def read_xlsx_rows(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    strings = [html.unescape(re.sub(r"<[^>]+>", "", s))
               for s in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]
    rows = []
    for name in sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)):
        xml = z.read(name).decode()
        for row in re.findall(r"<row [^>]*>(.*?)</row>", xml, re.S):
            cells = {}
            for col, attrs, body in re.findall(r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)', row, re.S):
                v = re.search(r"<v>(.*?)</v>", body or "", re.S)
                if 't="s"' in attrs and v:
                    cells[col] = strings[int(v.group(1))]
                elif 't="inlineStr"' in attrs:
                    cells[col] = html.unescape(re.sub(r"<[^>]+>", "", body or ""))
                elif v:
                    cells[col] = html.unescape(v.group(1))
            rows.append(cells)
    return rows


def ingest(path):
    data = open(path, "rb").read()
    title = os.path.basename(path)
    if data[:1] == b"{":
        d = json.loads(data)
        title = d.get("title", title)
        data = base64.b64decode(d["content"])
    if data[:2] != b"PK":
        fail("Not an xlsx file (expected the Drive download of the Sitemap Cache).")
    out, seen = [], set()
    for c in read_xlsx_rows(data):
        url = (c.get("A") or "").strip()
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "h1": re.sub(r"\s+", " ", html.unescape(c.get("B") or "")).strip(),
                    "lastmod": (c.get("C") or "")[:10], "kind": kind_of(url)})
    if not out:
        fail("No URLs found in the file.")
    os.makedirs(CACHE, exist_ok=True)
    with open(SITEMAP, "w") as f:
        json.dump({"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": title,
                   "count": len(out), "rows": out}, f, ensure_ascii=False)
    kinds = {}
    for r in out:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"Sitemap cache saved: {len(out)} URLs ({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))}).")


# ── status ───────────────────────────────────────────────────────────────────
def load_cache():
    if not os.path.exists(SITEMAP):
        return None
    return json.load(open(SITEMAP))


def age_days(cache):
    t = time.mktime(time.strptime(cache["fetched_at"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    return (time.time() - t) / 86400


def status():
    c = load_cache()
    if not c:
        print("Sitemap cache: MISSING. Download it with the Drive connector, then run ingest.")
    elif age_days(c) > TTL_DAYS:
        print(f"Sitemap cache: STALE ({age_days(c):.0f} days old, {c['count']} URLs). Download it again, then run ingest.")
    else:
        print(f"Sitemap cache: FRESH ({age_days(c):.1f} days old, {c['count']} URLs). No Drive download needed.")


# ── query ────────────────────────────────────────────────────────────────────
def query(slug, terms, top):
    c = load_cache()
    if not c:
        fail("Sitemap cache missing. Download it with the Drive connector, then run ingest.")
    snap_path = os.path.join(CACHE, slug, "snapshot.json")
    if not os.path.exists(snap_path):
        fail(f"No snapshot at {os.path.relpath(snap_path, REPO)}.")
    snap = json.load(open(snap_path))

    bag = {}      # stem -> weight, from the primary keyword and the post's headings
    phrases = []  # (stem set, weight): multi-word terms must match as phrases

    def add_bag(text, w):
        for st in stems(text):
            bag[st] = max(bag.get(st, 0), w)

    primary = ""
    run = os.path.join(CACHE, slug, "run.json")
    if os.path.exists(run):
        primary = (json.load(open(run)).get("keywords") or {}).get("primary", "")
    add_bag(primary, 3)
    if primary:
        phrases.append((set(stems(primary)), 3))
    add_bag(snap.get("h1", ""), 1.5)
    for b in snap["blocks"]:
        if b["type"] == "heading" and b["level"] in (2, 3):
            add_bag(b["text"], 1.5)
    for t in re.split(r"[,;\n]", terms):
        st = set(stems(t))
        if st:
            phrases.append((st, 3))

    linked = {norm_url(l["href"]) for l in snap["links"] if l["type"] == "internal"}
    self_url = norm_url(snap.get("final_url") or snap["url"])
    rows = [r for r in c["rows"] if r["kind"] in ("blog", "wiki")]
    cand = []
    for r in rows:
        slug_words = re.sub(r"[-_/]+", " ", r["url"].rstrip("/").rsplit("/", 1)[-1])
        cand.append((r, set(stems(r["h1"] + " " + slug_words))))
    df = {}
    for _, st in cand:
        for x in st:
            df[x] = df.get(x, 0) + 1
    n = max(len(cand), 1)
    idf = lambda x: math.log(1 + n / df.get(x, 1))

    blog, wiki, dropped_linked = [], [], 0
    for r, T in cand:
        u = norm_url(r["url"])
        if u == self_url:
            continue
        if u in linked:
            dropped_linked += 1
            continue
        score = sum(bag[x] * idf(x) for x in T if x in bag)
        for S, w in phrases:
            hit = S & T
            if hit and (len(S) <= 2 or len(hit) / len(S) >= 0.6):
                score += w * (len(hit) / len(S)) * sum(idf(x) for x in hit)
        score /= math.sqrt(max(len(T), 1))
        (blog if r["kind"] == "blog" else wiki).append((score, r))
    blog.sort(key=lambda x: -x[0])
    wiki = sorted((x for x in wiki if x[0] > 0), key=lambda x: -x[0])

    def path(u):
        return re.sub(r"^https?://[^/]+", "", u)

    print(f"Internal link candidates for {slug}. The post itself and {dropped_linked} pages it already links are excluded.")
    print("Base URL: https://www.seobility.net  (paths below are relative to it)")
    print(f"\nBLOG: all {len(blog)} remaining posts, best keyword matches first. Judge by meaning, not only by score.")
    for sc, r in blog:
        print(f"{sc:4.1f} | {path(r['url'])} | {r['h1'][:75]}")
    print(f"\nWIKI: top {min(top, len(wiki))} of {len(wiki)} matching entries (297 wiki pages in the sitemap).")
    for sc, r in wiki[:top]:
        print(f"{sc:4.1f} | {path(r['url'])} | {r['h1'][:60]}")


def main():
    a = sys.argv[1:]
    if not a:
        fail("Usage: refresh_sitemap.py status | ingest FILE | query SLUG [--terms \"a, b\"] [--top 20]")
    if a[0] == "status":
        status()
    elif a[0] == "ingest" and len(a) == 2:
        ingest(a[1])
    elif a[0] == "query" and len(a) >= 2:
        terms, top = "", 20
        if "--terms" in a:
            terms = a[a.index("--terms") + 1]
        if "--top" in a:
            top = int(a[a.index("--top") + 1])
        query(a[1], terms, top)
    else:
        fail("Usage: refresh_sitemap.py status | ingest FILE | query SLUG [--terms \"a, b\"] [--top 25]")


if __name__ == "__main__":
    main()
