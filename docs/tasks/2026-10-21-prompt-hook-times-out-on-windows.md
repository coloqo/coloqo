# The prompt hook times out on Windows after a break

## What happened

2026-10-21, the pilot team, plugin 0.5.0. A member on Windows sees, often, when they come back to a
session after a break and write in it:

```
UserPromptSubmit hook [uvx coloqo@0.5.0 hook user-prompt-submit] timed out after 10s — output discarded. Raise the hook's "timeout" to allow more time.
```

The members on macOS and Linux do not see it.

## Facts checked (2026-10-21)

- **The hook runs on every prompt** (`plugin/claude/hooks/hooks.json`, timeout 10 s) and does:
  start `uvx coloqo@0.5.0`; `POST /api/assistant` to register the session; `GET /api/inbox`
  unless the focus is `quiet` (`user_prompt_submit` in `hooks.py`).
- **Its network budget is not bounded as a whole.** `Api(timeout=3)` is httpx's timeout per phase
  (connect, read, write, pool), so two requests may take about 12 s before failing.
- **Startup on Linux:** `uvx coloqo@0.5.0 --version` takes 0.2 s here.
- **The server is the same for everyone**, so the cause is on the client: a cold start of Python
  (an antivirus scanning the interpreter and the environment again after idle), or the network
  waking up (DNS, TLS). Not measured on the member's machine yet.
- **What is lost:** the reminder of addressed messages and of the task's Topic for that prompt;
  the prompt itself goes through after the wait.

## To measure

After a break of 15–20 minutes, and again right after, in PowerShell:

```powershell
Measure-Command { uvx coloqo@0.5.0 --version }
Measure-Command { uvx coloqo@0.5.0 status }
```

The first is the startup alone, the second adds a request to the server.

## Ways to fix

1. **Raise the timeout.** Claude Code holds the prompt while the hook runs: the member waits longer.
2. **A total budget for the hook's network,** a few seconds; past it the reminder is skipped
   silently. No red line; a reminder is sometimes lost.
3. **No network in the hook.** The watch already receives the events; it keeps what concerns the
   session in a local file and the hook only reads it. Fast on any system; more work.

## Decided

2026-10-21, the author: postponed until the problem is diagnosed on the member's machine together
with them; no fix is chosen before that.
