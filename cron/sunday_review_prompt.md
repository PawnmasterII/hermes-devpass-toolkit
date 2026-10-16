Weekly ElectronHub effectiveness review. Do ALL of the following, then produce a compact digest:

1. Session census: open $HERMES_HOME/state.db (sqlite, read-only URI mode) and report:
   - sessions started this week, total input/output tokens this week
   - the 3 heaviest sessions by input_tokens (title + tokens)
   - how many sessions used delegate_task (messages.tool_calls LIKE '%delegate_task%')
2. Fan-out score: count subagent sessions this week (sessions.source='subagent') and their
   token share. Compare against last week if rows exist. Target trend: fan-out share rising,
   single-session token share falling.
3. Slot health: run a tiny probe request (any :dev model, max_tokens=4) and read the
   x-ratelimit-* / x-electronhub-service-mode headers. Report service mode. Then scan for
   stray Hermes processes (PowerShell: Get-CimInstance Win32_Process matching
   'hermes_cli|gateway run|hermes chat'; the desktop Hermes.exe tree and the
   discord_watcher pythonw are EXPECTED — everything else is a stray). Kill strays only
   if idle; otherwise list them.
4. Advice: exactly 3 bullets for next week based on the numbers (e.g. which heavy session
   should have been a fan-out; per docs/effectiveness_plan_TEMPLATE.md rules).

Format: short markdown digest, one table for the census, under 40 lines total.
Numbers first, no process narration.

Scheduling (when creating the cron):
  action=create, name="Weekly effectiveness review", schedule="every sunday 10am",
  skills=["delegation-playbook", "delegation-slot-config"]
