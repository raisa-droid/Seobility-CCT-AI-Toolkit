#!/usr/bin/env python3
"""Check every link in a /refresh snapshot: status, redirects, soft 404s, dirty links.

Usage:
  python3 scripts/refresh_links.py POST_SLUG            # every link in the snapshot
  python3 scripts/refresh_links.py --urls URL [URL…]    # just these links
  python3 scripts/refresh_links.py --md FILE SLUG       # links in a markdown draft that are not
                                                        # already in the snapshot (/refresh-fix
                                                        # checks the links it adds)
Add --json for the full JSON. The default prints a short summary: counts plus
only the links that need attention (the full results are saved to links.json).

Reads .refresh-cache/<slug>/snapshot.json (from refresh_crawl.py) and checks each
unique internal and external link (fragments, mailto and tel are skipped).

Verdicts:
  ok          final 2xx, no redirect
  redirect    final 2xx after redirects. redirect_kind "minor" = same page after
              normalizing (http→https, www, trailing slash); "moved" = different URL
  soft_404    redirected from a deeper path to a homepage or language root, or a 2xx
              page whose title says "404" / "not found"
  dead        final 4xx (except 401/403/429) or 5xx, DNS failure, timeout
  unverified  401/403/429/999: the site blocks bots, so the link can't be confirmed
              dead (X/Twitter, LinkedIn, Cloudflare). Never treat these as dead links.

Dirty links (independent of the verdict):
  ai_tracking  utm_source from an AI tool (chatgpt.com, perplexity, copilot, gemini,
               claude.ai, ...). -fix strips these silently; clean_url is given.
  affiliate    affiliate networks or affiliate-only parameters (Amazon tag=, ShareASale,
               Awin, CJ, Impact, PartnerStack, Rakuten, Skimlinks, ?fpr=, ?aff_id= ...).
  possible_affiliate  generic parameters that are often affiliate codes but can be plain
               referral labels (?ref=, ?via=, ?partner= ...). Claude judges.
  tracking     other tracking parameters (utm_*, gclid, fbclid, Mailchimp, HubSpot,
               Twitter embed ref_src ...). clean_url is given.

Uses curl (the Mac's system Python TLS is too old for some sites). One GET per
link, first 64 KB only, redirects followed, 10 links in parallel. Bot-blocked
links get a second check through DataForSEO on_page/instant_pages ($0.00015 per
link); sites that block DataForSEO too (e.g. searchengineland.com, tested
2026-10-01) stay unverified. A DataForSEO 3xx is reported as a redirect to its
Location without following further.
Writes .refresh-cache/<slug>/links.json and prints it. Standard library only.
"""
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refresh_api  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, ".refresh-cache")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
BOT_BLOCK = {401, 403, 429, 999}

AI_SOURCES = re.compile(r"^(chatgpt\.com|chat\.openai\.com|openai|perplexity(\.ai)?|copilot(\.microsoft\.com)?|"
                        r"bing\.com/chat|gemini(\.google\.com)?|bard|claude(\.ai)?|anthropic|you\.com|"
                        r"phind(\.com)?|deepseek|meta\.ai|grok)$", re.I)
TRACKING_PARAMS = re.compile(r"^(utm_[a-z]+|gclid|gbraid|wbraid|fbclid|msclkid|dclid|yclid|twclid|ttclid|"
                             r"mc_cid|mc_eid|_hsenc|_hsmi|__hstc|__hssc|__hsfp|hsctatracking|mkt_tok|"
                             r"ref_src|ref_url|igshid|si|s_kwcid|_ga|_gl|oly_anon_id|oly_enc_id|vero_id)$", re.I)
AFFILIATE_PARAMS = re.compile(r"^(aff|affid|aff_id|affiliate|affiliate_id|aff_sub\d?|fpr|irclickid|irgwc|"
                              r"sscid|ranmid|raneaid|ransiteid|awc|cjevent|cjdata|avad|tap_a|tap_s|rfsn|"
                              r"gr_pk)$", re.I)
# Generic names that are often affiliate codes but also plain referral labels (?ref=producthunt).
MAYBE_AFFILIATE_PARAMS = re.compile(r"^(ref|ref_id|refid|referral|via|partner|partner_id|pid|clickid|"
                                    r"click_id|deal|coupon)$", re.I)
AFFILIATE_HOSTS = re.compile(r"(^|\.)(amzn\.to|shareasale\.com|awin1\.com|anrdoezrs\.net|jdoqocy\.com|"
                             r"tkqlhce\.com|dpbolvw\.net|kqzyfj\.com|emjcd\.com|sjv\.io|pxf\.io|"
                             r"impactradius\.com|ojrq\.net|hop\.clickbank\.net|linksynergy\.com|"
                             r"go\.skimresources\.com|redirect\.viglink\.com|prf\.hn|clk\.tradedoubler\.com|"
                             r"avantlink\.com|partnerstack\.com|grsm\.io|refersion\.com|tapfiliate\.com|"
                             r"shrsl\.com)$", re.I)
NOT_FOUND_TITLE = re.compile(r"\b(404|page not found|not found|page doesn.t exist|page does not exist|"
                             r"no longer available)\b", re.I)


def fail(msg):
    print(json.dumps({"data_available": False, "error": msg}))
    sys.exit(1)


def norm(url):
    p = urllib.parse.urlsplit(url)
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    host = re.sub(r":(80|443)$", "", host)
    return host + (p.path.rstrip("/") or "") + ("?" + p.query if p.query else "")


def is_root(path):
    """Homepage or a bare language root like /en/ or /en-us/."""
    return bool(re.fullmatch(r"/?([a-z]{2}([-_][a-z]{2})?/?)?", path.lower()))


def dirty(url):
    p = urllib.parse.urlsplit(url)
    host = p.netloc.lower()
    params = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    keys = [k for k, _ in params]
    kinds, matched = [], []

    src = dict((k.lower(), v) for k, v in params).get("utm_source", "")
    if src and AI_SOURCES.match(src.lower().replace("https://", "").replace("www.", "").rstrip("/")):
        kinds.append("ai_tracking")
        matched.append(f"utm_source={src}")

    aff = [k for k in keys if AFFILIATE_PARAMS.match(k)]
    if host.endswith(("amazon.com", "amazon.co.uk", "amazon.de")) and "tag" in keys:
        aff.append("tag")
    if AFFILIATE_HOSTS.search(host):
        kinds.append("affiliate")
        matched.append(f"network:{host}")
    if aff:
        if "affiliate" not in kinds:
            kinds.append("affiliate")
        matched += aff
    maybe = [k for k in keys if MAYBE_AFFILIATE_PARAMS.match(k)]
    if maybe:
        if "affiliate" not in kinds:
            kinds.append("possible_affiliate")
        matched += maybe
    trk = [k for k in keys if TRACKING_PARAMS.match(k)]
    if trk and "ai_tracking" not in kinds:
        kinds.append("tracking")
        matched += trk
    elif "ai_tracking" in kinds:
        matched += [k for k in trk if k.lower() != "utm_source"]

    if not kinds:
        return None
    drop = {k.lower() for k in keys if TRACKING_PARAMS.match(k)}
    clean_q = urllib.parse.urlencode([(k, v) for k, v in params if k.lower() not in drop])
    clean = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, clean_q, p.fragment))
    return {"kinds": kinds, "matched": sorted(set(matched)), "clean_url": clean}


def check(url):
    with tempfile.NamedTemporaryFile() as hdr:
        cmd = ["curl", "-sL", "--compressed", "--max-redirs", "10", "--max-time", "20",
               "-r", "0-65535", "-A", UA, "-H", "Accept: text/html,*/*;q=0.8",
               "-H", "Accept-Language: en-US,en;q=0.9",
               "-D", hdr.name, "-o", "-", "-w", "\n@@CURL@@%{http_code}\t%{url_effective}", url]
        r = subprocess.run(cmd, capture_output=True)
        headers = open(hdr.name, "rb").read().decode(errors="replace")
    body, _, meta = r.stdout.rpartition(b"\n@@CURL@@")
    code, _, final = meta.decode(errors="replace").partition("\t")
    chain = [int(m) for m in re.findall(r"^HTTP/[\d.]+ (\d{3})", headers, re.M)]
    if r.returncode != 0 and not chain:
        reason = {6: "DNS failure", 7: "connection refused", 28: "timeout",
                  35: "TLS error", 47: "too many redirects", 60: "TLS certificate error"}.get(r.returncode, f"curl error {r.returncode}")
        return {"status": None, "final_status": None, "final_url": None, "hops": 0, "error": reason}
    final_status = int(code) if code.isdigit() and code != "000" else (chain[-1] if chain else None)
    # Range requests are answered with 206 by servers that honor them.
    final_status = 200 if final_status == 206 else final_status
    title = ""
    m = re.search(rb"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1).decode(errors="replace")).strip()
    return {"status": chain[0] if chain else final_status, "final_status": final_status,
            "final_url": final or url, "hops": max(0, len(chain) - 1), "title": title[:200]}


def verdict(url, res):
    st = res["final_status"]
    if res.get("error"):
        return "dead", None
    if st in BOT_BLOCK:
        return "unverified", None
    if st is None or st >= 400:
        return "dead", None
    src, dst = urllib.parse.urlsplit(url), urllib.parse.urlsplit(res["final_url"])
    redirected = res["hops"] > 0
    if redirected and is_root(dst.path) and not is_root(src.path):
        return "soft_404", None
    if res.get("title") and NOT_FOUND_TITLE.search(res["title"]):
        return "soft_404", None
    if redirected:
        a, b = norm(url).split("?")[0], norm(res["final_url"]).split("?")[0]
        # twitter.com → x.com with the same path is the rebrand, not a moved page.
        a = re.sub(r"^(mobile\.)?twitter\.com", "x.com", a)
        return "redirect", "minor" if a == b else "moved"
    return "ok", None


def check_dataforseo(url):
    """Second opinion for bot-blocked links: DataForSEO's crawler, $0.00015 per link."""
    try:
        item = refresh_api.dfs_post("https://api.dataforseo.com/v3/on_page/instant_pages",
                                    [{"url": url}], timeout=60)["tasks"][0]["result"][0]["items"][0]
    except Exception:
        return None
    st = item.get("status_code")
    if not isinstance(st, int) or st in BOT_BLOCK:
        return None
    loc = item.get("location")
    return {"status": st, "final_status": st, "final_url": loc or url,
            "hops": 1 if loc else 0, "title": ((item.get("meta") or {}).get("title") or "")[:200]}


def check_all(hrefs):
    """Check links, retrying bot-blocked ones through DataForSEO. Returns (results, checked_via)."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = dict(zip(hrefs, pool.map(check, hrefs)))
    hook = refresh_api.dfs_configured()
    blocked = [h for h, r in results.items() if r["final_status"] in BOT_BLOCK]
    checked_via = {}
    if hook and blocked:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            for h, r in zip(blocked, pool.map(lambda u: check_dataforseo(u), blocked)):
                if r:
                    results[h] = r
                    checked_via[h] = "dataforseo"
    return results, checked_via


def short(u, n=95):
    return u if len(u) <= n else u[:n - 1] + "…"


def compact(result, label):
    """Counts plus only the links that need attention. Unverified links are grouped by site."""
    v = result["verdicts"]
    print(f"LINKS {label}: {result['checked']} checked | " + ", ".join(f"{k} {n}" for k, n in sorted(v.items())))
    unverified = {}
    for r in result["links"]:
        verdict_ = r["verdict"]
        if verdict_ == "ok":
            pass
        elif verdict_ == "unverified":
            host = re.sub(r"^https?://([^/]+).*$", r"\1", r["href"])
            unverified.setdefault(host, []).append(r["href"])
        else:
            kind = f"/{r['redirect_kind']}" if r.get("redirect_kind") else ""
            where = f" | block {','.join(r['blocks'])}" if r.get("blocks") else ""
            anchor = f" | anchor \"{r['anchors'][0][:40]}\"" if r.get("anchors") else ""
            err = f" | {r['error']}" if r.get("error") else ""
            arrow = f" -> {short(r['final_url'])}" if r.get("final_url") and r["final_url"] != r["href"] else ""
            print(f" {verdict_}{kind} {r.get('final_status') or ''} | {short(r['href'])}{arrow}{where}{anchor}{err}")
    for host, hrefs in unverified.items():
        print(f" unverified (site blocks bots, never report as dead): {host} x{len(hrefs)}")
    for r in result["links"]:
        d = r.get("dirty")
        if d:
            print(f" dirty {'+'.join(d['kinds'])} | {short(r['href'])} | clean: {short(d['clean_url'])}")


def check_urls(urls, as_json=False, label="(new links)"):
    results, checked_via = check_all(urls)
    out = []
    for u in urls:
        res = results[u]
        v, kind = verdict(u, res)
        row = {"href": u, "verdict": v, **({"redirect_kind": kind} if kind else {}),
               "final_status": res["final_status"], "final_url": res["final_url"],
               **({"checked_via": checked_via[u]} if u in checked_via else {}),
               **({"error": res["error"]} if res.get("error") else {})}
        d = dirty(u)
        if d:
            row["dirty"] = d
        out.append(row)
    counts = {}
    for r in out:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    result = {"data_available": True, "checked": len(out), "verdicts": counts, "links": out}
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        compact(result, label)
    return result


def main():
    as_json = "--json" in sys.argv
    argv = [a for a in sys.argv[1:] if a != "--json"]
    if argv and argv[0] == "--urls":
        urls = list(dict.fromkeys(a for a in argv[1:] if a.startswith("http")))
        if not urls:
            fail("Usage: refresh_links.py --urls URL [URL ...]")
        check_urls(urls, as_json)
        return
    if argv and argv[0] == "--md" and len(argv) == 3:
        md, slug = argv[1], argv[2]
        snap_path = os.path.join(CACHE, slug, "snapshot.json")
        if not os.path.exists(md) or not os.path.exists(snap_path):
            fail("Usage: refresh_links.py --md FILE SLUG (needs the markdown file and the snapshot)")
        known = {l["href"].split("#")[0].rstrip("/").lower() for l in json.load(open(snap_path))["links"]}
        found = re.findall(r"\[[^\]]*\]\((https?://[^)\s]+)\)", open(md).read())
        found = [u for u in dict.fromkeys(found) if "claude.ai/artifact" not in u and "docs.google.com" not in u]
        new = [u for u in found if u.split("#")[0].rstrip("/").lower() not in known]
        if not new:
            print(f"LINKS (new in draft): none. All {len(found)} links in the draft are already in the snapshot.")
            return
        res = check_urls(new, as_json, label=f"(new in draft; {len(found) - len(new)} unchanged)")
        # Non-zero exit when the draft needs edits, so a && chain stops before the next step.
        needs_edit = any(r["verdict"] in ("dead", "soft_404") or r.get("redirect_kind") == "moved" or r.get("dirty")
                         for r in res["links"])
        if needs_edit:
            print("-> Edit the draft for the links above, then run this check again.")
            sys.exit(3)
        return
    if len(argv) != 1:
        fail("Usage: refresh_links.py POST_SLUG | --urls URL [URL ...] | --md FILE SLUG")
    slug = argv[0]
    snap_path = os.path.join(CACHE, slug, "snapshot.json")
    if not os.path.exists(snap_path):
        fail(f"No snapshot at {os.path.relpath(snap_path, REPO)}. Run refresh_crawl.py first.")
    snap = json.load(open(snap_path))

    links = {}
    for l in snap["links"]:
        if l["type"] not in ("internal", "external"):
            continue
        href = l["href"].split("#")[0] if l["type"] == "internal" else l["href"]
        entry = links.setdefault(href, {"href": href, "type": l["type"], "anchors": [], "blocks": []})
        if l.get("anchor_text") and l["anchor_text"] not in entry["anchors"]:
            entry["anchors"].append(l["anchor_text"])
        if l.get("block") and l["block"] not in entry["blocks"]:
            entry["blocks"].append(l["block"])

    # Bot-blocked links get a second check through DataForSEO's crawler.
    results, checked_via = check_all(list(links))

    out = []
    for href, entry in links.items():
        res = results[href]
        v, kind = verdict(href, res)
        row = {**entry, "verdict": v, **({"redirect_kind": kind} if kind else {}),
               "status": res["status"], "final_status": res["final_status"],
               "final_url": res["final_url"], "hops": res["hops"],
               **({"checked_via": checked_via[href]} if href in checked_via else {})}
        if res.get("error"):
            row["error"] = res["error"]
        if v == "soft_404" and res.get("title"):
            row["final_title"] = res["title"]
        d = dirty(href)
        if d:
            row["dirty"] = d
        out.append(row)

    order = {"dead": 0, "soft_404": 1, "redirect": 2, "unverified": 3, "ok": 4}
    out.sort(key=lambda r: (order[r["verdict"]], r["type"], r["href"]))
    counts = {}
    for r in out:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    dirty_counts = {}
    for r in out:
        for k in (r.get("dirty") or {}).get("kinds", []):
            dirty_counts[k] = dirty_counts.get(k, 0) + 1

    result = {"data_available": True, "slug": slug, "checked": len(out),
              "verdicts": counts, "dirty": dirty_counts, "links": out}
    with open(os.path.join(CACHE, slug, "links.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        compact(result, f"in {slug}")
        print(" full results: " + os.path.relpath(os.path.join(CACHE, slug, "links.json"), REPO))


if __name__ == "__main__":
    main()
