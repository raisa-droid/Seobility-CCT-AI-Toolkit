#!/usr/bin/env python3
"""Resolve the approval-page decisions for /refresh-fix and check the gate.

Usage:
  python3 scripts/refresh_decisions.py --dir DIR [--no-compare] [--no-snapshot]

DIR is the out_dir given to the ArtifactData tool, holding
  DIR/run/findings.json          (get run/findings)
  DIR/decisions/<ID>.json        (list decisions; each file is {decision, note, ...})

What it does, in one call (these were about five exploratory turns):
  1. Resolves every item: Decide items (info gain, FAQ, other) apply on Y and are
     skipped on n; unanswered blocks the run. Applied items apply unless skipped;
     required items always apply. A note travels with its item.
  2. Checks the gate: every Decide item answered, at least one info gain Yes
     (unless meta.info_gain_required is false), FAQ block ends at 3-6 questions.
     Same rules as the status bar on the approval page.
  3. Checks whether the live post changed since the -analyze crawl
     (refresh_crawl.py --compare).
  4. On a pass: prints the apply list with each item's fix text and note, a NOTES list
     (the notes are binding and replace any fix text they contradict), the skipped
     list, the silent link fixes and, unless --no-snapshot, the saved snapshot text.
     Writes .refresh-cache/<slug>/apply.json. Bash output over about 30,000 characters
     is saved to a file that must then be read in full, so /refresh-fix uses
     --no-snapshot and prints the snapshot in the next turn.

Exit code 0 = gate passed, 2 = gate failed (nothing to apply). Standard library only.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, ".refresh-cache")


def die(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def load_decisions(folder):
    out = {}
    if not os.path.isdir(folder):
        return out
    for name in os.listdir(folder):
        if name.endswith(".json"):
            try:
                d = json.load(open(os.path.join(folder, name)))
            except ValueError:
                continue
            dec = (d.get("decision") or "").strip()
            dec = "Y" if dec.lower() in ("y", "yes") else "n" if dec.lower() in ("n", "no") else ""
            out[name[:-5]] = {"decision": dec, "note": (d.get("note") or "").strip()}
    return out


def main():
    a = sys.argv[1:]
    if "--dir" not in a:
        die("Usage: refresh_decisions.py --dir DIR [--no-compare] [--no-snapshot]")
    base = a[a.index("--dir") + 1]
    fpath = os.path.join(base, "run", "findings.json")
    if not os.path.exists(fpath):
        die(f"No findings at {fpath}. Run ArtifactData get run/findings with out_dir first.")
    findings = json.load(open(fpath))
    meta = findings.get("meta", {})
    items = findings.get("items", [])
    slug = meta.get("slug", "")
    decisions = load_decisions(os.path.join(base, "decisions"))

    apply_list, skipped, problems = [], [], []
    faq_count = 0
    has_faq = any(i["bucket"] == "faq" for i in items)
    info_yes = 0
    info_total = sum(1 for i in items if i["bucket"] == "info_gain")
    for it in items:
        d = decisions.get(it["id"], {"decision": "", "note": ""})
        decide_bucket = it["bucket"] in ("info_gain", "faq", "decide")
        if decide_bucket:
            if d["decision"] == "":
                problems.append(f"{it['id']} isn't answered ({it['title'][:70]})")
                continue
            apply = d["decision"] == "Y"
        else:
            apply = it.get("required") or d["decision"] != "n"
        if it["bucket"] == "info_gain" and d["decision"] == "Y":
            info_yes += 1
        if it["bucket"] == "faq":
            act = (it.get("action") or "").lower()
            if act.startswith("keep") or act == "replace":
                faq_count += 1
            elif act == "add" and apply:
                faq_count += 1
            elif act == "cut" and not apply:
                faq_count += 1
        row = {"id": it["id"], "bucket": it["bucket"], "section": it.get("section", ""), "title": it["title"],
               "action": it.get("action"), "note": d["note"], "required": bool(it.get("required")),
               "checklist": it.get("checklist", []), "fix": (it.get("details") or {}).get("fix", ""),
               "decision": d["decision"]}
        (apply_list if apply else skipped).append(row)

    if info_total and meta.get("info_gain_required", True) and info_yes < 1:
        problems.append("Pick at least one info gain item (all are No or unanswered).")
    if has_faq and not 3 <= faq_count <= 6:
        problems.append(f"The FAQ block would have {faq_count} questions; it needs 3 to 6.")

    print(f"POST: {meta.get('h1', '?')} | {meta.get('url', '?')} | slug {slug}")
    print(f"APPROVAL PAGE: {meta.get('approval_url', '?')}")
    if problems:
        print("GATE: FAIL. Nothing was applied. Fix these on the approval page, then run /refresh-fix again:")
        for p in problems:
            print(f" - {p}")
        sys.exit(2)
    print(f"GATE: PASS. {len(apply_list)} to apply, {len(skipped)} skipped. FAQ block: {faq_count} questions.")

    if "--no-compare" not in a and meta.get("url"):
        r = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "refresh_crawl.py"), meta["url"], "--compare"],
                           capture_output=True, text=True)
        try:
            cmp = json.loads(r.stdout)
        except ValueError:
            cmp = {}
        if not cmp.get("data_available"):
            print(f"LIVE PAGE: couldn't be checked ({cmp.get('error', 'no response')}).")
        elif cmp.get("changed"):
            print(f"LIVE PAGE: CHANGED since the -analyze crawl ({cmp['snapshot_crawled_at']}). Ask the user whether to continue on the snapshot.")
            for k, v in cmp.get("meta_changes", {}).items():
                print(f"  {k}: snapshot '{v['snapshot'][:80]}' -> live '{v['live'][:80]}'")
            for b in cmp.get("blocks_removed", [])[:8]:
                print(f"  removed {b['id']}: {b['text'][:100]}")
            for b in cmp.get("blocks_added", [])[:8]:
                print(f"  added: {b['text'][:100]}")
        else:
            print(f"LIVE PAGE: unchanged since the -analyze crawl ({cmp.get('snapshot_crawled_at')}).")

    os.makedirs(os.path.join(CACHE, slug), exist_ok=True)
    json.dump({"apply": apply_list, "skipped": skipped, "faq_questions": faq_count},
              open(os.path.join(CACHE, slug, "apply.json"), "w"), ensure_ascii=False, indent=2)

    print(f"\nAPPLY ({len(apply_list)}), in this order: new sections and restructures, edits in place, replacements:")
    order = {"info_gain": 0, "faq": 0, "decide": 1, "applied": 2}
    for r in sorted(apply_list, key=lambda r: (order.get(r["bucket"], 3), r["id"])):
        tag = " [REQUIRED]" if r["required"] else ""
        print(f"\n[{r['id']}] {r['bucket']}{tag} | {r['section']}\n  {r['title']}")
        if r["fix"]:
            print(f"  FIX: {r['fix']}")
        if r["note"]:
            print(f"  NOTE FROM USER (binding, see the NOTES list below): {r['note']}")
        print(f"  checklist: {', '.join(r['checklist']) or '-'}")
    noted = [r for r in apply_list if r["note"]]
    if noted:
        print(f"\nNOTES ({len(noted)}). Each one is the user's instruction and REPLACES any part of that item's fix text or title it contradicts."
              " Before writing, state in one line per note what you will do differently from the fix text. A note is not satisfied by copying the AFTER text.")
        for r in noted:
            print(f" - {r['id']}: {r['note']}")
    print(f"\nSKIPPED ({len(skipped)}):")
    for r in skipped:
        why = "answered No" if r["bucket"] != "applied" else "skipped on the page"
        print(f" - {r['id']} ({why}): {r['title'][:90]}" + (f" | note: {r['note']}" if r["note"] else ""))

    links_path = os.path.join(CACHE, slug, "links.json")
    if os.path.exists(links_path):
        silent = []
        for l in json.load(open(links_path)).get("links", []):
            if l.get("redirect_kind") == "minor" and l.get("final_url"):
                silent.append(f" - minor redirect: {l['href']} -> {l['final_url']}")
            d = l.get("dirty") or {}
            if d and set(d.get("kinds", [])) <= {"ai_tracking", "tracking"}:
                silent.append(f" - tracking tags: {l['href']} -> {d['clean_url']}")
        if silent:
            print(f"\nSILENT LINK FIXES (apply without logging them; same destination):")
            print("\n".join(silent))

    snap = os.path.join(CACHE, slug, "snapshot.md")
    if "--no-snapshot" not in a and os.path.exists(snap):
        text = open(snap).read()
        text = text.split("\n## Links")[0]   # the links are inline in the blocks; this keeps the output under the 30k-character inline limit
        print(f"\nSNAPSHOT ({os.path.relpath(snap, REPO)}), the exact crawled copy to edit:\n")
        print(text)


if __name__ == "__main__":
    main()
