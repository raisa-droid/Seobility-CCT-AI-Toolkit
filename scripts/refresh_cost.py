#!/usr/bin/env python3
"""Exact Claude token use and API-equivalent cost of past /refresh runs.

Usage:
  python3 scripts/refresh_cost.py [--last N] [--dir TRANSCRIPT_DIR]

Claude Code saves every chat as a transcript with exact token counts per step.
This finds the /refresh-analyze and /refresh-fix runs in them (several per chat
are split at each command), adds the tokens up and prices them. It replaces the
in-command token report, which only had approximate context sizes and cost two
extra turns per run.

Prices are API list prices per million tokens (input, output, cache read);
cache writes are 1.25x input for the 5-minute TTL and 2x for the 1-hour TTL.
On a Team plan these runs are not billed per token; the dollars show what the
same tokens would cost through the API and which model and design is cheaper.
The external APIs (DataForSEO, Gemini) are not included: they were about $0.09
per cycle at the last measurement. Standard library only.
"""
import glob
import json
import os
import re
import sys

PRICES = {  # input, output, cache read ($ per million tokens)
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}
MARK = re.compile(r"<command-name>/(refresh-(?:analyze|fix))</command-name>")
ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)


def default_dir():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.expanduser("~/.claude/projects/" + re.sub(r"[^A-Za-z0-9]", "-", repo))


def text_of(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def runs_in(path):
    runs, cur, seen = [], None, {}
    for line in open(path, errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") == "user":
            t = text_of(r.get("message", {}))
            m = MARK.search(t)
            if m and t.lstrip().startswith("<command-message>"):
                a = ARGS.search(t)
                cur = {"command": m.group(1), "args": (a.group(1).strip() if a else ""), "start": r.get("timestamp", ""),
                       "msgs": {}}
                runs.append(cur)
        elif r.get("type") == "assistant" and cur is not None:
            msg = r.get("message", {})
            u = msg.get("usage")
            if u and msg.get("id"):
                cur["msgs"][msg["id"]] = (msg.get("model", ""), u)  # last chunk of a message has the final counts
    return runs


def cost_of(run):
    t = {"turns": 0, "input": 0, "w5": 0, "w1": 0, "read": 0, "out": 0}
    models = set()
    for model, u in run["msgs"].values():
        models.add(model)
        t["turns"] += 1
        t["input"] += u.get("input_tokens", 0)
        t["read"] += u.get("cache_read_input_tokens", 0)
        t["out"] += u.get("output_tokens", 0)
        cc = u.get("cache_creation") or {}
        w5, w1 = cc.get("ephemeral_5m_input_tokens"), cc.get("ephemeral_1h_input_tokens")
        if w5 is None and w1 is None:
            w5, w1 = u.get("cache_creation_input_tokens", 0), 0
        t["w5"] += w5 or 0
        t["w1"] += w1 or 0
    model = next(iter(models)) if len(models) == 1 else "mixed"
    p = next((v for k, v in PRICES.items() if model.startswith(k)), None)
    if p is None:
        return t, model, None
    i, o, rd = p
    usd = (t["input"] * i + t["w5"] * i * 1.25 + t["w1"] * i * 2 + t["read"] * rd + t["out"] * o) / 1e6
    return t, model, usd


def main():
    a = sys.argv[1:]
    last = int(a[a.index("--last") + 1]) if "--last" in a else 8
    d = a[a.index("--dir") + 1] if "--dir" in a else default_dir()
    files = glob.glob(os.path.join(d, "*.jsonl"))
    if not files:
        print(f"No transcripts found in {d}")
        sys.exit(1)
    rows = []
    for f in files:
        for run in runs_in(f):
            if run["msgs"]:
                rows.append(run)
    rows.sort(key=lambda r: r["start"])
    rows = rows[-last:]
    if not rows:
        print("No /refresh-analyze or /refresh-fix runs found in the transcripts.")
        return
    print(f"{'started':16} {'command':16} {'model':18} {'turns':>5} {'new ctx':>8} {'reads':>7} {'output':>7} {'cost':>7}  arg")
    total = 0.0
    for r in rows:
        t, model, usd = cost_of(r)
        total += usd or 0
        arg = re.sub(r"https?://(www\.)?seobility\.net/en/blog/", "", r["args"])[:46]
        cost = f"${usd:5.2f}" if usd is not None else "  n/a"
        print(f"{r['start'][:16]:16} {r['command']:16} {model:18} {t['turns']:>5} {(t['w5'] + t['w1']) // 1000:>7}k "
              f"{t['read'] // 1000:>6}k {t['out'] // 1000:>6}k {cost:>7}  {arg}")
    print(f"\nTotal for the runs shown: ${total:.2f} (API-equivalent list prices; Claude only, external APIs excluded).")
    print("new ctx = tokens written to the cache (content read in, plus Claude's own output); reads = cached tokens re-read every turn.")


if __name__ == "__main__":
    main()
