#!/usr/bin/env python
"""Configure Hermes delegation around your DevPass slot pool.

Reads nothing secret; writes ONLY via `hermes config set` (never hand-edits
config.yaml). Safe to re-run.

Logic:
  - Detect DevPass tier from a live probe (RPM limit header: 8=Lite, 20=Turbo).
  - children = slots - 1 (reserve one for the parent/user turn).
  - Child model: first arg --child-model, else first of
    [--child-model-candidates] that the key can actually call (default starts
    with deepseek-v4.1-flash:dev). Every candidate must be a 1-slot model.
  - streaming left alone unless --streaming on|off is passed.

Usage:
  python configure_delegation.py
  python configure_delegation.py --child-model deepseek-v4.1-flash:dev
  python configure_delegation.py --streaming on
"""
import argparse, json, os, re, subprocess, sys, urllib.request, urllib.error

HERMES = os.environ.get("HERMES_HOME", os.path.join(os.path.expanduser("~"), ".hermes"))
DEFAULT_CANDIDATES = ["deepseek-v4.1-flash:dev", "glm-5.3-flash:dev", "qwen3.8-27b:dev"]
HEAVY = {"glm-5.3:dev"}          # 2-slot models: never select as child model

def env_key():
    k = os.environ.get("ELECTRONHUB_API_KEY", "").strip()
    if k:
        return k
    p = os.path.join(HERMES, ".env")
    if os.path.exists(p):
        env = dict(re.findall(r"^([A-Z_0-9]+)=(.*)$", open(p, encoding="utf-8").read(), re.M))
        return env.get("ELECTRONHUB_API_KEY", "").strip()
    return ""

def probe(key):
    """-> (tier_slots, dev_models)"""
    slots, dev_models = None, []
    req = urllib.request.Request("https://api.electronhub.ai/v1/models",
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            dev_models = [m.get("id") for m in json.load(r).get("data", [])
                          if str(m.get("id", "")).endswith(":dev")]
    except Exception as e:
        print(f"warn: models probe failed ({e}); will trust requested model verbatim")
    req = urllib.request.Request(
        "https://api.electronhub.ai/v1/chat/completions",
        data=json.dumps({"model": dev_models[0] if dev_models else "glm-5.3-flash:dev",
                         "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 4}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read(); h = dict(r.headers)
        lim = int(h.get("x-ratelimit-limit", 0) or 0)
        slots = {8: 2, 20: 5}.get(lim)          # Lite=2, Turbo=5
    except Exception as e:
        print(f"warn: header probe failed ({e}); tier unknown")
    return slots, dev_models

def hermes(*args):
    r = subprocess.run(["hermes", *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"`hermes {' '.join(args)}` failed:\n{r.stderr}")
    return r.stdout.strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--child-model", help="pin this exact child model (must be 1-slot)")
    ap.add_argument("--child-model-candidates", nargs="*", default=DEFAULT_CANDIDATES)
    ap.add_argument("--streaming", choices=["on", "off"])
    ap.add_argument("--key", help="explicit API key (else env / $HERMES_HOME/.env)")
    args = ap.parse_args()

    key = args.key or env_key()
    if not key:
        sys.exit("No API key found (env ELECTRONHUB_API_KEY or $HERMES_HOME/.env).")

    slots, dev_models = probe(key)
    if slots is None:
        slots = 5
        print("tier not detected -> assuming Turbo (5 slots); pass a valid key for exactness")
    children = slots - 1
    print(f"slots: {slots} -> max_concurrent_children: {children}")

    # choose child model
    child = args.child_model
    if child and child in HEAVY:
        sys.exit(f"refusing: {child} is a Heavy (2-slot) model — never use as child")
    if not child:
        for cand in args.child_model_candidates:
            if cand in HEAVY:
                continue
            if not dev_models or cand in dev_models:
                child = cand
                break
        if not child:
            sys.exit(f"none of {args.child_model_candidates} visible to this key; pass --child-model")
    print(f"child model: {child}")

    hermes("config", "set", "delegation.max_concurrent_children", str(children))
    hermes("config", "set", "delegation.model", child)
    if args.streaming:
        hermes("config", "set", "model.streaming", "true" if args.streaming == "on" else "false")

    print("\nverify:")
    for k in ("delegation.max_concurrent_children", "delegation.model",
              *(() if not args.streaming else ("model.streaming",))):
        print(f"  {k} = {hermes('config', 'get', k)}")
    print("\nDone. See ../docs/effectiveness_plan_TEMPLATE.md for the operating rules.")

if __name__ == "__main__":
    main()
