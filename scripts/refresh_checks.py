#!/usr/bin/env python3
"""Mechanical SEO checks on a /refresh snapshot (no API call, standard library only).

Usage:
  python3 scripts/refresh_checks.py POST_SLUG --kw "primary keyword"
  python3 scripts/refresh_checks.py POST_SLUG --kw "primary keyword" --faq "question 1" "question 2"

Reads .refresh-cache/<slug>/snapshot.json (from refresh_crawl.py) and prints a short
report; the full result is saved to checks.json. It only measures: Claude decides
which results become findings. Checks:

  Metadata   H1 count, title length (50-60), meta description length (120-155),
             years in the H1/title/meta that are older than this year
  Keyword    close-variant presence in H1, title, meta, intro (everything before the
             first H2, the "In this post" box included) and every H2/H3; keyword
             stuffing (variant occurrences per 100 words, and per paragraph)
  Anchors    links whose anchor text is under 3 words (jump links are skipped)
  Products   product links (seobility.net pages that are not /blog, /wiki or the
             home page, plus register links), where they sit and how many are body links
  Paragraphs paragraphs over 4 sentences (-fix splits these silently, no finding)
  FAQ        --faq questions, plus the questions of an existing FAQ section, compared
             with the rest of the post: is the question already answered in the body?

Close variants: articles, pronouns, determiners, prepositions, auxiliaries and
question words are ignored; the rest of the keyword's words are matched by a light
stem (plural, -ing, -ed). "full" = every core word is present, "partial" = some
are missing (they are listed), "none" = no core word is present. Word order and
words in between don't matter, same rule as /refresh-analyze Step 9.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, ".refresh-cache")

# Words that don't change what the keyword is about.
IGNORE = set("""a an the your you yours my our their its his her this that these those and or but nor of to in on for
with at by from as into over about is are be am was were been being do does did can could should would will shall may
might must need needs i we it they he she what which who whom whose when where why how than then there here so not no""".split())

ABBREV = re.compile(r"\b(e\.g|i\.e|vs|etc|approx|inc|ltd|no|fig|dr|mr|mrs|ms|u\.s|u\.k|a\.m|p\.m|st)\.", re.I)
CAP_START = re.compile(r"""(?<=[.!?])["”’)\]]*\s+(?=["“‘(\[]?[A-Z0-9])""")

FAQ_HEADING = re.compile(r"\bfaqs?\b|frequently asked|common questions|questions about", re.I)
PRODUCT_CAPS = "Top 1, Middle 2, Bottom 2 (judge against the confirmed funnel; a dedicated Seobility section and the closing CTA don't count)"


def stem(w):
    w = w.lower().replace("'", "").replace("’", "")
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 5 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and re.search(r"(ss|x|ch|sh|z)es$", w):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
        w = w[:-1]
    return w[:6]  # 6-letter prefix: optimize / optimization / optimizing all match


def tokens(text):
    return re.findall(r"[a-z0-9]+(?:['’][a-z]+)?", text.lower())


def core_stems(text):
    """Ordered, de-duplicated core stems of a phrase."""
    out = []
    for t in tokens(text):
        if t in IGNORE:
            continue
        s = stem(t)
        if s not in out:
            out.append(s)
    return out


def stem_set(text):
    return {stem(t) for t in tokens(text) if t not in IGNORE}


def variant_status(text, core):
    have = stem_set(text)
    missing = [c for c in core if c not in have]
    if not missing:
        return "full", []
    if len(missing) == len(core):
        return "none", missing
    return "partial", missing


def count_occurrences(text, core):
    """Occurrences of the keyword as a variant: all core stems inside a window of len(core)+3 tokens."""
    if not core:
        return 0
    toks = [stem(t) for t in tokens(text) if t not in IGNORE]
    window = len(core) + 3
    need = set(core)
    count, i = 0, 0
    while i < len(toks):
        if toks[i] in need:
            seg = toks[i:i + window]
            if need <= set(seg):
                count += 1
                # jump past the last core word of this occurrence
                last = max(j for j, s in enumerate(seg) if s in need and s not in seg[j + 1:])
                i += last + 1
                continue
        i += 1
    return count


def sentences(text):
    t = ABBREV.sub(lambda m: m.group(0).replace(".", "\u2024"), text)
    t = re.sub(r"(?<=\d)\.(?=\d)", "\u2024", t)
    t = re.sub(r"\b([A-Z])\.(?=\s?[A-Z]\.|\s[a-z])", "\\1\u2024", t)
    parts = [p.strip() for p in CAP_START.split(t) if p.strip()]
    return [p.replace("\u2024", ".") for p in parts]


def short(text, n=60):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def link_label(href):
    p = urllib.parse.urlparse(href)
    path = p.path.rstrip("/")
    if "seobility.net" in p.netloc:
        return (p.netloc.replace("www.", "") if p.netloc.startswith("app.") else "") + path
    return p.netloc.replace("www.", "") + path


def classify_link(href):
    """product / brand_home / content (blog, wiki) / other (external) for a link."""
    p = urllib.parse.urlparse(href)
    host = p.netloc.lower()
    path = p.path.rstrip("/")
    if host.startswith("app.seobility.net") or "/register" in path:
        return "register"
    if "seobility.net" not in host:
        return "external"
    if re.match(r"^/[a-z]{2}$", path) or path == "":
        return "brand_home"
    if re.search(r"/(blog|wiki)(/|$)", path):
        return "content"
    return "product"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--kw", required=True)
    ap.add_argument("--faq", nargs="*", default=[])
    args = ap.parse_args()

    snap_path = os.path.join(CACHE, args.slug, "snapshot.json")
    if not os.path.exists(snap_path):
        sys.exit(f"No snapshot at {snap_path}. Run refresh_crawl.py first.")
    snap = json.load(open(snap_path))
    blocks = snap["blocks"]
    core = core_stems(args.kw)
    core_words = [t for t in tokens(args.kw) if t not in IGNORE]
    this_year = datetime.date.today().year
    result = {"slug": args.slug, "keyword": args.kw, "core_words": core_words}

    # sections: block id -> (current H2 text)
    section_of, cur = {}, "(before first H2)"
    first_h2_idx = next((i for i, b in enumerate(blocks) if b["type"] == "heading" and b.get("level") == 2), len(blocks))
    for b in blocks:
        if b["type"] == "heading" and b.get("level") == 2:
            cur = b["text"]
        section_of[b["id"]] = cur
    words_total = snap["stats"]["words"]

    # ---- metadata
    h1, title, meta = snap["h1"], snap["title"], snap["meta_description"]
    tl, ml = snap["title_length"], snap["meta_description_length"]
    meta_lines = []
    n_h1 = snap["h1_count"]
    meta_lines.append(f"H1 count: {n_h1}" + ("" if n_h1 == 1 else "  ← FLAG (needs exactly 1)"))
    meta_lines.append(f"Title tag: {tl} chars (target 50–60)" + ("" if 50 <= tl <= 60 else "  ← FLAG"))
    meta_lines.append(f"Meta description: {ml} chars (target 120–155)" + ("" if 120 <= ml <= 155 else "  ← FLAG"))
    old_years = {}
    for label, text in (("H1", h1), ("title", title), ("meta", meta)):
        ys = sorted({int(y) for y in re.findall(r"\b(20[0-3]\d)\b", text) if int(y) < this_year})
        if ys:
            old_years[label] = ys
    meta_lines.append("Outdated years: " + ("; ".join(f"{k} has {', '.join(map(str, v))}" for k, v in old_years.items()) + "  ← FLAG"
                                          if old_years else f"none older than {this_year}"))
    result["metadata"] = {"h1_count": n_h1, "title_length": tl, "meta_length": ml, "outdated_years": old_years}

    # ---- keyword variants
    intro_blocks = blocks[:first_h2_idx]
    intro_text = " ".join(b["text"] for b in intro_blocks)
    intro_ids = f"{intro_blocks[0]['id']}–{intro_blocks[-1]['id']}" if intro_blocks else "none"

    def fmt(st):
        s, missing = st
        return s if s == "full" else f"{s}, missing: {', '.join(missing)}"

    places = {
        "H1": variant_status(h1, core),
        "Title": variant_status(title, core),
        "Meta": variant_status(meta, core),
        f"Intro ({intro_ids})": variant_status(intro_text, core),
    }
    kw_lines = [f"Core words: {', '.join(core_words)}  (ignored: articles, pronouns, prepositions, auxiliaries, question words)"]
    for k, st in places.items():
        kw_lines.append(f"{k}: {fmt(st)}")
    # earliest core word in the title, to judge "keyword near the front"
    tt = title.lower()
    pos = [m.start() for c in core for m in [re.search(re.escape(c[:max(3, len(c) - 1)]), tt)] if m]
    if pos:
        kw_lines.append(f"Title: first keyword word starts at char {min(pos)}")
    heads = [b for b in blocks if b["type"] == "heading" and b.get("level") in (2, 3)]
    hits = [b for b in heads if variant_status(b["text"], core)[0] == "full"]
    kw_lines.append(f"Headings with the keyword (H2/H3): {len(hits)} of {len(heads)}"
                    + ("" if not hits else " → " + "; ".join(f'{b["id"]} "{short(b["text"], 50)}"' for b in hits)))
    result["keyword"] = {"core": core_words, "places": {k: {"status": v[0], "missing": v[1]} for k, v in places.items()},
                         "headings_with_keyword": [b["id"] for b in hits], "headings_total": len(heads)}

    # stuffing
    body = [b for b in blocks if b["type"] != "heading"]
    per_block = {b["id"]: count_occurrences(b["text"], core) for b in body}
    total = sum(per_block.values()) + sum(count_occurrences(b["text"], core) for b in heads)
    density = total / words_total * 100 if words_total else 0
    heavy = [f"{i} ({n}×)" for i, n in per_block.items() if n >= 3]
    stuff = density > 2.0 or bool(heavy)
    kw_lines.append(f"Occurrences in body and headings: {total} in {words_total} words = {density:.1f} per 100 words"
                    + ("  ← FLAG possible stuffing (over 2.0)" if density > 2.0 else "")
                    + (f"  ← FLAG 3+ in one block: {', '.join(heavy)}" if heavy else ""))
    result["keyword"]["occurrences"] = total
    result["keyword"]["per_100_words"] = round(density, 2)
    result["keyword"]["stuffing"] = stuff

    # ---- anchors under 3 words
    short_anchors = {}
    empty = []
    for l in snap["links"]:
        if l["type"] == "fragment":
            continue
        a = " ".join((l.get("anchor_text") or "").split())
        if not a:
            empty.append((l["block"], l["href"]))
            continue
        if len(a.split()) < 3:
            short_anchors.setdefault((a, l["href"]), []).append(l["block"])
    anc_lines = [f"{len(short_anchors)} distinct links with an anchor under 3 words" + (f", {len(empty)} with no anchor text" if empty else "")]
    for (a, href), bl in short_anchors.items():
        anc_lines.append(f'  {", ".join(bl)}  "{a}" → {link_label(href)} [{classify_link(href)}]')
    for b_, href in empty:
        anc_lines.append(f"  {b_}  (no anchor text, probably an image link) → {link_label(href)}")
    result["short_anchors"] = [{"anchor": a, "href": h, "blocks": bl, "kind": classify_link(h)} for (a, h), bl in short_anchors.items()]

    # ---- product links
    last_h2 = next((b["text"] for b in reversed(blocks) if b["type"] == "heading" and b.get("level") == 2), None)
    prod = []
    for l in snap["links"]:
        k = classify_link(l["href"])
        if k in ("product", "register"):
            prod.append({"block": l["block"], "anchor": " ".join((l.get("anchor_text") or "").split()), "href": l["href"],
                         "kind": k, "section": section_of.get(l["block"], "?")})
    body_links = [p for p in prod if p["kind"] == "product" and p["section"] != last_h2]
    last_links = [p for p in prod if p["kind"] == "product" and p["section"] == last_h2]
    regs = [p for p in prod if p["kind"] == "register"]
    homes = [l for l in snap["links"] if classify_link(l["href"]) == "brand_home"]
    prod_lines = [f"Product links: {len(body_links)} in the body, {len(last_links)} in the last section"
                  f"{' (' + short(last_h2, 40) + ')' if last_h2 else ''}, {len(regs)} register/trial, {len(homes)} to the home page",
                  f"Caps: {PRODUCT_CAPS}"]
    for p in prod:
        prod_lines.append(f'  {p["block"]}  [{p["kind"]}] "{short(p["anchor"], 40)}" → {link_label(p["href"])}  (in: {short(p["section"], 35)})')
    result["product_links"] = {"body": len(body_links), "last_section": len(last_links), "register": len(regs),
                               "home": len(homes), "items": prod, "last_section_title": last_h2}

    # ---- long paragraphs
    long_p = []
    for b in blocks:
        if b["type"] == "paragraph" and not b.get("boxed"):
            n = len(sentences(b["text"]))
            if n > 4:
                long_p.append((b["id"], n))
    par_lines = [f"{len(long_p)} paragraphs over 4 sentences (-fix splits these silently, not a finding)"
                 + (": " + ", ".join(f"{i} ({n})" for i, n in long_p) if long_p else "")]
    result["long_paragraphs"] = [{"block": i, "sentences": n} for i, n in long_p]

    # ---- FAQ vs body overlap
    faq_start = None
    faq_qs = []
    for i, b in enumerate(blocks):
        if b["type"] == "heading" and b.get("level") == 2 and FAQ_HEADING.search(b["text"]):
            faq_start = i
            for c in blocks[i + 1:]:
                if c["type"] == "heading" and c.get("level") == 2:
                    break
                if c["type"] == "heading" and c.get("level") == 3:
                    faq_qs.append((c["id"], c["text"]))
            break
    faq_end = len(blocks)
    if faq_start is not None:
        faq_end = next((j for j in range(faq_start + 1, len(blocks))
                        if blocks[j]["type"] == "heading" and blocks[j].get("level") == 2), len(blocks))
    outside = [b for k, b in enumerate(blocks) if not (faq_start is not None and faq_start <= k < faq_end)]
    questions = [(f"existing {i}", q) for i, q in faq_qs] + [("candidate", q) for q in args.faq]
    faq_lines = []
    faq_res = []
    if faq_start is not None:
        faq_lines.append(f'Existing FAQ section "{short(blocks[faq_start]["text"], 40)}" ({blocks[faq_start]["id"]}): {len(faq_qs)} H3 questions')
    elif questions:
        faq_lines.append("No existing FAQ section found")
    for src, q in questions:
        qs = stem_set(q)
        if not qs:
            continue
        best_h, best_b = (0, None), (0, None)
        for b in outside:
            r = len(qs & stem_set(b["text"])) / len(qs)
            if b["type"] == "heading":
                if r > best_h[0]:
                    best_h = (r, b)
            elif r > best_b[0]:
                best_b = (r, b)
        verdict = "no close match"
        enough = len(qs) >= 3
        if best_h[1] is not None and best_h[0] >= 0.99 and enough:
            verdict = f'LIKELY ANSWERED: heading {best_h[1]["id"]} "{short(best_h[1]["text"], 40)}" covers every core word'
        elif best_b[1] is not None and best_b[0] >= 0.99 and enough:
            verdict = f'POSSIBLY ANSWERED: {best_b[1]["id"]} has every core word'
        elif not enough and best_b[1] is not None and best_b[0] >= 0.99:
            verdict = f'core words all in {best_b[1]["id"]} (question too short to judge, check by reading)'
        else:
            bits = []
            if best_h[1] is not None and best_h[0] >= 0.6:
                bits.append(f'closest heading {best_h[1]["id"]} {best_h[0]:.0%}')
            if best_b[1] is not None and best_b[0] >= 0.6:
                bits.append(f'closest text {best_b[1]["id"]} {best_b[0]:.0%}')
            if bits:
                verdict = "partial overlap: " + ", ".join(bits)
        faq_lines.append(f'  [{src}] "{short(q, 70)}" → {verdict}')
        faq_res.append({"source": src, "question": q, "verdict": verdict})
    result["faq_overlap"] = faq_res
    if not questions:
        faq_lines.append("No FAQ questions given or found (pass --faq \"question\" … to check candidates)")

    # ---- print
    out = [f"CHECKS {args.slug}  (keyword: \"{args.kw}\")", "", "Metadata"] + ["  " + l for l in meta_lines] + \
          ["", "Keyword (close variants)"] + ["  " + l for l in kw_lines] + \
          ["", "Anchors"] + ["  " + l if not l.startswith("  ") else l for l in anc_lines] + \
          ["", "Products"] + ["  " + l if not l.startswith("  ") else l for l in prod_lines] + \
          ["", "Paragraphs"] + ["  " + l for l in par_lines] + \
          ["", "FAQ vs body"] + ["  " + l if not l.startswith("  ") else l for l in faq_lines]
    text = "\n".join(out)
    json.dump(result, open(os.path.join(CACHE, args.slug, "checks.json"), "w"), indent=1, ensure_ascii=False)
    print(text)


if __name__ == "__main__":
    main()
