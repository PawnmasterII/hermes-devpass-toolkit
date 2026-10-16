#!/usr/bin/env python
"""Probe an ElectronHub key: model access, RPM budget, service mode, queue class.

Usage:
    python slot_probe.py                 # uses DISCORD_BOT_TOKEN-free env: reads ELECTRONHUB_API_KEY
    ELECTRONHUB_API_KEY=ek-dev-... python slot_probe.py

Prints (never prints the key):
    - which :dev models the key can see
    - x-ratelimit-limit / remaining  (RPM starts, NOT concurrency slots)
    - service-mode and queue headers (interactive / priority vs slow lane)
    - daily headroom units remaining

Concurrency slots themselves are not reported by the API; consult your plan
(Lite=2, Turbo=5) and the docs. This probe confirms the key works and which
lane you're in.
"""
import json, os, re, sys, urllib.request, urllib.error

def load_key():
    k = os.environ.get("ELECTRONHUB_API_KEY", "").strip()
    if k:
        return k, "environment"
    home = os.environ.get("HERMES_HOME", os.path.join(os.path.expanduser("~"), ".hermes"))
    p = os.path.join(home, ".env")
    if os.path.exists(p):
        env = dict(re.findall(r"^([A-Z_0-9]+)=(.*)$", open(p, encoding="utf-8").read(), re.M))
        k = env.get("ELECTRONHUB_API_KEY", "").strip()
        if k:
            return k, p
    sys.exit("No ELECTRONHUB_API_KEY in environment or $HERMES_HOME/.env")

def main():
    key, src = load_key()
    print(f"key source: {src} | kind: {'DevPass (ek-dev-)' if key.startswith('ek-dev-') else 'standard'}")

    # models
    req = urllib.request.Request("https://api.electronhub.ai/v1/models",
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ids = [m.get("id") for m in json.load(r).get("data", [])]
        devs = [i for i in ids if i and ":dev" in i]
        print(f"models visible: {len(ids)} | :dev models: {len(devs)}")
        for i in devs:
            print("   ", i)
    except urllib.error.HTTPError as e:
        print("models endpoint failed:", e.code)

    # one tiny request for headers
    model = devs[0] if devs else "glm-5.3-flash:dev"
    req = urllib.request.Request(
        "https://api.electronhub.ai/v1/chat/completions",
        data=json.dumps({"model": model, "messages": [{"role": "user", "content": "Say OK"}],
                         "max_tokens": 4}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read(); code, h = r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        e.read(); code, h = e.code, dict(e.headers)

    print(f"\nprobe model: {model} -> HTTP {code}")
    for k in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset",
              "x-electronhub-service-mode", "x-electronhub-queue",
              "x-ratelimit-daily-limit", "x-ratelimit-daily-remaining"):
        if h.get(k):
            print(f"  {k}: {h[k]}")

    lim = int(h.get("x-ratelimit-limit", 0) or 0)
    if lim:
        tier = {8: "Lite (2 slots)", 20: "Turbo (5 slots)"}.get(lim, f"custom (limit {lim})")
        print(f"\n=> DevPass tier guess: {tier}")
    mode = h.get("x-electronhub-service-mode", "")
    if mode and mode != "interactive":
        print("=> NOTE: you are in a paced service mode; expect queued starts.")
    daily_rem = int(h.get("x-ratelimit-daily-remaining", 0) or 0)
    daily_lim = int(h.get("x-ratelimit-daily-limit", 0) or 0)
    if daily_lim:
        print(f"=> daily full-speed units: {daily_rem:,} / {daily_lim:,} "
              f"({daily_rem/daily_lim:.0%} free before the soft lane)")

if __name__ == "__main__":
    main()
