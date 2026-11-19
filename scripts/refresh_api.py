"""Shared DataForSEO access for the refresh scripts (see also _api.sh).

Webhook mode (DATAFORSEO_WEBHOOK_URL) or direct mode (DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD),
read from .env or the environment. The webhook wins when both are set.
"""
import base64
import json
import os
import re
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env():
    env = {}
    path = os.path.join(REPO, ".env")
    if os.path.exists(path):
        for line in open(path):
            m = re.match(r"\s*([A-Z_]+)\s*=\s*(.*)\s*$", line)
            if m:
                env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    for k, v in os.environ.items():
        if k.startswith("DATAFORSEO_") and v:
            env[k] = v
    return env


def dfs_configured():
    e = load_env()
    return bool(e.get("DATAFORSEO_WEBHOOK_URL") or (e.get("DATAFORSEO_LOGIN") and e.get("DATAFORSEO_PASSWORD")))


def dfs_post(endpoint, body, timeout=90):
    """POST one DataForSEO request and return the parsed JSON. Raises RuntimeError if not configured."""
    e = load_env()
    if e.get("DATAFORSEO_WEBHOOK_URL"):
        url = e["DATAFORSEO_WEBHOOK_URL"]
        data = json.dumps({"endpoint": endpoint, "body": body}).encode()
        headers = {"Content-Type": "application/json"}
    elif e.get("DATAFORSEO_LOGIN") and e.get("DATAFORSEO_PASSWORD"):
        url = endpoint
        data = json.dumps(body).encode()
        auth = base64.b64encode(f"{e['DATAFORSEO_LOGIN']}:{e['DATAFORSEO_PASSWORD']}".encode()).decode()
        headers = {"Content-Type": "application/json", "Authorization": f"Basic {auth}"}
    else:
        raise RuntimeError("DataForSEO is not configured (DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD, or DATAFORSEO_WEBHOOK_URL)")
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
