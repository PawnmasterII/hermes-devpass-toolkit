# Effectiveness Plan — TEMPLATE

Copy this file, fill the census row with your own audit, and keep it next to your skills.
Doctrine verified on an ElectronHub DevPass Turbo key; numbers marked *measured* come from
live probes — re-measure on your own key before trusting exact figures.

## 1. What you're paying for (and not using)

| Resource | DevPass gives | Typical use | Verdict |
|---|---|---|---|
| Tokens | Unlimited | — | Free real estate — never ration |
| Full-speed units | Daily soft headroom, resets 21:00 UTC | few % | Vast surplus |
| Concurrency slots | **Lite 2 / Turbo 5 per key** | peaks 1-2 | **The only scarce thing** |
| RPM | 8 Lite / 20 Turbo (burst 4/8) | rarely binding | Non-issue |

**The rule:** tokens are free, slots are scarce. Every decision = more parallel streams, never fewer tokens.

## 2. Model routing

| Tier | Example `:dev` ids | Slots | Route to it |
|---|---|---|---|
| Flash 0.5× | glm-5.3-flash, deepseek-v4-flash, mimo-v2.5 | 1 | Bulk grinding, long docs, unattended volume |
| Standard 1× | deepseek-v4.1-flash, qwen3.8-27b, minimax-m2.7 | 1 | Delegation children, quality-parallel work |
| Heavy 2× | glm-5.3 | **2** | Main session only, hardest single problem. NEVER a child. |

*Measured:* 2 parallel Standard streams beat 1 faster Flash stream ~1.6× on the same two units of work, plus failure isolation. Width beats speed. Spawn overhead (~20-30s/batch) dominates small jobs — don't fan out trivia.

## 3. Workload playbooks

- **Doc pipelines** (proposals, diffs, extraction): one child per document/version, N-wide; parent judges 2KB digests. Hours → minutes.
- **Research/scouting**: 4 children, one per source family (docs / GitHub / registries / community), each returns a ranked digest. Never serially ingest dozens of sources into one context.
- **Stateful tooling** (game editors, live apps): parent drives inline; delegate only the parallel research and mechanical audits around it.
- **Single-artifact work** (exams, one essay): keep inline — no fan-out win.
- **Messaging**: sleep the gateway when unused (watcher does this on demand) so nothing competes for slots.

## 4. Session hygiene — the hidden ratio

Long sessions re-send their entire context every turn; a *measured* 12:1 input:output ratio is normal unmanaged drift.
- One task = one session. Done → new session.
- A parent drifting past ~200 messages should have been a fan-out.
- Compression is reactive; delegation is the proactive fix.

## 5. Slot etiquette

- children = slots − 1 (reserve one for the live user turn). Turbo → 4.
- Ledger: open at dispatch (`children_cost + 1 if chatting`), close at batch-complete.
- 429 + `Retry-After≈3` = over the pool — recount immediately. `x-ratelimit-remaining` counts RPM starts, NOT slots.
- The pool is per-key and cross-model: mixing families never adds capacity.
- Sweep strays (gateway/CLI leftovers) before big fan-outs.

## 6. Don'ts

- No Heavy children. No model-family mixing for capacity. No hundreds of concurrency 429s in a day (triggers a multi-hour 403 pause). Don't ration tokens.

## 7. My audit (fill in)

| Metric | Value |
|---|---|
| Sessions audited | |
| Fan-out sessions | |
| Subagent token share | |
| Heaviest serial session | |
| Actions taken | |
