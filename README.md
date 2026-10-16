# Hermes DevPass Toolkit

Make an ElectronHub **DevPass** (Coding Plan) key + Hermes Agent delegation behave at full effectiveness — and keep it that way with zero-maintenance automation.

> **Why this exists.** DevPass keys bill flat (unlimited tokens) but have a small pool of **concurrency slots** (2 on Lite, 5 on Turbo) shared by *everything* using the key: your main session, every delegation child, every stray CLI/gateway process. The toolkit configures Hermes around that reality, adds live slot discipline, and wires a Discord bot that sleeps (0 slots) until you ping it.

## What you get

| Piece | What it does |
|---|---|
| `setup/configure_delegation.py` | Probes your key (tier, slots, RPM, service mode), then sets the right `delegation.*` values in Hermes (children count, child model pin). Idempotent. |
| `watcher/discord_watcher.py` | Zero-LLM Discord listener: `@yourbot wake` spawns `hermes gateway`, `sleep` kills it, `status` reports. Costs **no API slots while idle**. |
| `setup/install_watcher.ps1` | Registers the watcher as a Windows logon Scheduled Task (auto-restart, no window). |
| `lib/slot_probe.py` | One-call slot/RPM headroom probe against your key (reads `x-ratelimit-*` headers). |
| `skills/` | Two ready-to-install Hermes skills: `delegation-playbook` (fan-out rules, model routing, measured width-vs-speed numbers) and `delegation-slot-config` (configure + slot ledger + stray-process sweep). |
| `cron/sunday_review_prompt.md` | Prompt template for a weekly Hermes cron that audits your sessions, fan-out usage, and slot health. |
| `docs/effectiveness_plan_TEMPLATE.md` | The operating doctrine: tokens are free, slots are the only currency; workload playbooks; session hygiene. |

## Requirements

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed (`hermes` on PATH)
- An ElectronHub API key — DevPass (`ek-dev-…`) for `:dev` models. A regular key works too; slot counts differ.
- *(Optional, for the watcher)* a Discord bot token — put it in `$HERMES_HOME/.env` as `DISCORD_BOT_TOKEN`, plus `DISCORD_ALLOWED_USERS` (comma-separated usernames allowed to command it) and `DISCORD_HOME_CHANNEL` (channel ID for keyword commands).

## Quickstart

```bash
git clone https://github.com/PawnmasterII/hermes-devpass-toolkit.git
cd hermes-devpass-toolkit

# 1. See what your key actually allows (tier, slots, RPM)
python lib/slot_probe.py

# 2. Configure Hermes delegation to match (writes via `hermes config set`)
python setup/configure_delegation.py

# 3. Optional: Discord wake/sleep watcher (Windows)
powershell -File setup/install_watcher.ps1
```

Then, in Discord: **@yourbot wake** / **@yourbot sleep** / **@yourbot status**.

## The model that makes this work

DevPass concurrency (per key, **cross-model** — verified empirically; 5 requests in flight on model A will 429 a request to model B):

| Series | Example `:dev` ids | Slots/req | Lite (2) | Turbo (5) |
|---|---|---|---|---|
| Flash 0.5× | `glm-5.3-flash`, `deepseek-v4-flash`, `mimo-v2.5` | 1 | 2 parallel | 5 parallel |
| Standard 1× | `deepseek-v4.1-flash`, `qwen3.8-27b`, `minimax-m2.7` | 1 | 2 parallel | 5 parallel |
| Heavy 2× | `glm-5.3` | **2** | 1 | 2 (+1 slot left) |

Rules encoded by the toolkit:

1. **Tokens are free; slots are the only currency.** Never ration output — maximize useful parallelism.
2. **Reserve one slot for the parent.** Turbo → `max_concurrent_children: 4`. Lite → 1.
3. **Never Heavy children.** Two `glm-5.3:dev` kids = 4 of 5 slots gone.
4. **Width beats speed.** Measured: 2 parallel Standard streams finish the same work ~1.6× faster than 1 faster Flash stream, and one stalled child no longer loses the batch.
5. **Mixing model families gains nothing** — the pool is per-key. (429 + `Retry-After≈3` means you're over; recount.)
6. **One task = one session.** Long serial sessions re-send their whole context every turn; delegation children absorb bulk for a ~2 KB digest.

## How the watcher stays free

A Hermes gateway holds a Discord websocket + can burn model slots the moment a message arrives. The watcher is a plain websocket listener (no LLM, no provider calls): idle cost is zero slots and a few MB of RAM. The real gateway exists only while you're actually using Discord — and you decide when that is.

```
@bot wake    ->  watcher spawns `hermes gateway run` (detached), confirms when state file says connected
@bot sleep   ->  watcher taskkill /T the gateway tree, confirms death
@bot status  ->  reads gateway_state.json + checks the pid is alive
```

Safety: only usernames in `DISCORD_ALLOWED_USERS` can command it. It never reads message content beyond the command line; message-content intent is used only to parse `wake/sleep/status`.

## Installing the skills

```bash
cp -r skills/delegation-playbook  "$HOME/.hermes/skills/"    # or your skills dir
cp -r skills/delegation-slot-config "$HOME/.hermes/skills/"
hermes skills list                 # verify both appear
```

## Weekly self-audit (optional but recommended)

Create a Hermes cron from `cron/sunday_review_prompt.md` (paste its contents as the prompt, schedule `every sunday 10am`). Each week you get: session census, fan-out score, slot health, and three concrete actions — benchmarked against `docs/effectiveness_plan_TEMPLATE.md`.

## Compatibility

- **OS:** Windows first-class (watcher install + process sweep are PowerShell). `slot_probe.py`, `configure_delegation.py`, skills, and cron template are cross-platform; on macOS/Linux run the gateway under your own supervisor instead of the scheduled task.
- **Hermes:** config keys `delegation.max_concurrent_children`, `delegation.model`, `model.streaming` — present in current releases.
- Not affiliated with ElectronHub, Nous Research, or Discord. Uses only public APIs.

## License

MIT — see [LICENSE](LICENSE).
