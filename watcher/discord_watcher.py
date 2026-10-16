#!/usr/bin/env python
"""Hermes Discord wake-on-ping watcher.

Zero-LLM, zero-ElectronHub-slot listener. Holds the Discord bot websocket and
spawns/kills the real `hermes gateway` process on command:

    @Hermes         / "hermes wake"   -> start gateway (reply when up)
    @Hermes sleep   / "hermes sleep"  -> kill gateway  (reply when down)
    @Hermes status  / "hermes status" -> report gateway state

Runs windowless via pythonw; registered as a logon Scheduled Task.
"""
import asyncio, json, os, re, subprocess, sys, time, io

HOME     = os.environ.get("HERMES_HOME", os.path.join(os.path.expanduser("~"), ".hermes"))
VENV_PY  = os.environ.get(
    "HERMES_PYTHON",
    os.path.join(HOME, "hermes-agent", "venv", "Scripts", "python.exe")
    if os.name == "nt" else "python3",
)
AGENTDIR = os.environ.get("HERMES_AGENT_DIR", os.path.join(HOME, "hermes-agent"))
LOGDIR   = os.path.join(HOME, "logs")
GWLOG    = os.environ.get("HERMES_GATEWAY_LOG", os.path.join(LOGDIR, "gateway-manual.log"))
STATE    = os.environ.get("HERMES_GATEWAY_STATE", os.path.join(HOME, "gateway_state.json"))
WATCHLOG = os.environ.get("HERMES_WATCHER_LOG", os.path.join(LOGDIR, "discord_watcher.log"))
HOME_CHANNEL = os.environ.get("DISCORD_HOME_CHANNEL", "")
API = "https://discord.com/api/v10"
WS  = "wss://gateway.discord.gg/?v=10&encoding=json"

# Windows detached-process flags; POSIX just inherits
DETACHED = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if os.name == "nt" else 0

ENV = load_env()
TOKEN = ENV.get("DISCORD_BOT_TOKEN", "")
ALLOWED = [u.strip() for u in re.split(r"[,\s]+", ENV.get("DISCORD_ALLOWED_USERS", "")) if u.strip()]

def pid_alive(pid):
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        return str(pid) in (r.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def gateway_status():
    """-> (running: bool, pid: int|None)"""
    try:
        d = json.load(open(STATE, encoding="utf-8"))
        pid = d.get("pid")
        if d.get("gateway_state") == "running" and pid and pid_alive(pid):
            return True, pid
    except (OSError, ValueError):
        pass
    return False, None

def spawn_gateway():
    running, pid = gateway_status()
    if running:
        return True, pid
    os.makedirs(os.path.dirname(GWLOG), exist_ok=True)
    lf = io.open(GWLOG, "ab")
    py = VENV_PY if os.path.exists(VENV_PY) else sys.executable
    subprocess.Popen(
        [py, "-m", "hermes_cli.main", "gateway", "run"],
        cwd=AGENTDIR, stdout=lf, stderr=lf,
        creationflags=DETACHED,
    )
    for _ in range(40):                      # gateway writes state within ~15s
        time.sleep(1)
        running, pid = gateway_status()
        if running:
            return True, pid
    return False, None

def kill_gateway():
    running, pid = gateway_status()
    if not running:
        return True, None
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True, timeout=30)
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(2)
    running, _ = gateway_status()
    return (not running), pid

import aiohttp

async def reply(http, channel_id, text):
    try:
        await http.post(f"{API}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {TOKEN}"},
            json={"content": text, "allowed_mentions": {"parse": []}})
    except Exception as e:
        await log(f"reply failed: {e!r}")

def parse_command(content, me_id):
    """-> 'wake' | 'sleep' | 'status' | None. A direct @mention counts as the trigger word."""
    c = (content or "").lower()
    mentioned = bool(re.search(rf"<@!?{me_id}>", c))
    c = c.replace(f"<@{me_id}>", " ").replace(f"<@!{me_id}>", " ")
    if not (mentioned or re.search(r"\bhermes\b", c)):
        return None
    if re.search(r"\b(wake|start|up)\b", c):          return "wake"
    if re.search(r"\b(sleep|stop|down|off)\b", c):    return "sleep"
    if re.search(r"\bstatus\b", c):                   return "status"
    return None

async def handle(http, me_id, msg):
    ch   = msg.get("channel_id")
    author = (msg.get("author") or {}).get("id", "")
    uname  = (msg.get("author") or {}).get("username", "").lower()
    if ALLOWED and author not in ALLOWED and uname not in [a.lower() for a in ALLOWED]:
        return
    mentioned = f"<@{me_id}>" in (msg.get("content") or "")
    cmd = parse_command(msg.get("content"), me_id)
    if not cmd:
        return
    if not (mentioned or ch == HOME_CHANNEL):
        return
    await log(f"cmd={cmd} ch={ch} by={author}")
    if cmd == "wake":
        await reply(http, ch, "Waking the gateway…")
        ok, pid = await asyncio.get_event_loop().run_in_executor(None, spawn_gateway)
        await reply(http, ch, "🟢 Gateway is up — I'm live here." if ok
                    else "⚠️ Spawn attempted but state didn't confirm; check logs/gateway-manual.log")
    elif cmd == "sleep":
        ok, pid = await asyncio.get_event_loop().run_in_executor(None, kill_gateway)
        await reply(http, ch, "😴 Gateway stopped. Ping me to wake it." if ok
                    else "⚠️ Tried to stop but the process is still alive.")
    elif cmd == "status":
        running, pid = gateway_status()
        await reply(http, ch, f"🟢 Gateway running (pid {pid})." if running
                    else "⚪ Gateway asleep — say **wake** to bring me online.")

async def heartbeat(ws, interval, seq):
    try:
        while True:
            await asyncio.sleep(interval)
            await ws.send_str(json.dumps({"op": 1, "d": seq[0]}))
    except Exception:
        pass

async def session_loop(http):
    async with http.ws_connect(WS, heartbeat=None) as ws:
        hello = json.loads((await ws.receive()).data)
        interval = hello["d"]["heartbeat_interval"] / 1000.0
        await ws.send_str(json.dumps({"op": 2, "d": {
            "token": TOKEN,
            "intents": (1 << 0) | (1 << 9) | (1 << 15),   # GUILDS | GUILD_MESSAGES | MESSAGE_CONTENT
            "properties": {"os": "windows", "browser": "hermes-watcher", "device": "hermes-watcher"},
        }}))
        seq = [None]
        hb = asyncio.create_task(heartbeat(ws, interval, seq))
        try:
            async for m in ws:
                d = json.loads(m.data)
                if d.get("s") is not None:
                    seq[0] = d["s"]
                if d.get("op") == 0 and d.get("t") == "READY":
                    await log(f"READY as {d['d']['user']['username']} ({d['d']['user']['id']})")
                elif d.get("op") == 0 and d.get("t") == "MESSAGE_CREATE":
                    asyncio.create_task(handle(http, d["d"].get("application_id") or "", d["d"]))
        finally:
            hb.cancel()

async def main():
    if not TOKEN:
        await log("FATAL: DISCORD_BOT_TOKEN missing"); return
    async with aiohttp.ClientSession() as http:
        r = await http.get(f"{API}/users/@me", headers={"Authorization": f"Bot {TOKEN}"})
        me = await r.json(content_type=None)
        me_id = str(me.get("id", "")) if isinstance(me, dict) else ""
        await log(f"watcher up, bot={me.get('username', '?')} id={me_id}")
        backoff = 5
        while True:
            try:
                await session_loop(http)
                backoff = 5
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await log(f"ws dropped: {e!r} — reconnect in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
