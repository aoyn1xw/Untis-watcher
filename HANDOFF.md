# Untis Watcher — Handoff & Next Steps

A running log of what's been built, what was fixed, and what to do next.

---

## What's Been Built

Untis Watcher is a Python bot that polls WebUntis every 5 minutes, diffs the timetable against a saved baseline (`state.json`), and sends a Telegram notification when anything changes.

### File Overview

| File | Purpose |
|------|---------|
| `main.py` | Entry point. Poll loop, login retry, health monitoring, tray icon |
| `timetable.py` | WebUntis login + fetch (JSON-RPC and REST API) |
| `detector.py` | Normalise and diff two timetable snapshots |
| `ai.py` | Format change summaries (structured fallback or AI model) |
| `notifier.py` | Send Telegram messages |
| `storage.py` | Load/save `state.json` |
| `health.py` | Track cycle outcomes, send alerts on repeated failures |
| `config.py` | Load all config from `.env` |
| `setup.py` | Interactive onboarding wizard — run once to create `.env` |
| `selftest.py` | Self-test suite |
| `state.json` | Persisted timetable baseline — **not committed to git** |
| `.env` | All secrets — **not committed to git** |

### Key Config Variables (`.env`)

```
UNTIS_SERVER        # e.g. heiken.webuntis.com
UNTIS_SCHOOL        # school slug from URL
UNTIS_USER
UNTIS_PASSWORD
UNTIS_ELEMENT_ID    # your student ID
UNTIS_ELEMENT_TYPE  # 5 = student (default)
TELEGRAM_TOKEN
TELEGRAM_CHAT_ID
POLL_INTERVAL       # seconds, default 300
DAYS_AHEAD          # default 7
AI_ENABLED          # true/false
AI_API_KEY
AI_BASE_URL
AI_MODEL
```

---

## What Was Fixed This Session

### Cancellations showing as "details updated"
**Problem:** Untis marks cancelled lessons with `code="cancelled"` but keeps them in the timetable. The differ correctly produced a `type="changed"` entry, but `ai.py` only checked for room/teacher/time diffs in the `changed` branch — cancellations had none, so they silently fell through to `"details updated"`.

**Fix (commit `e084138`):** Added `_is_cancelled()` helper in `ai.py`. The `changed` branch now checks:
1. `was_normal → now_cancelled` → `🔺 CANCELLED: Subject at HH:MM — free period!`
2. `was_cancelled → now_normal` → `➕ REINSTATED: Subject at HH:MM — Teacher, room X`
3. Code/status changed but no named field diff → `status normal → irregular` instead of `details updated`

### Setup wizard added
**Commit `92ce062`:** `setup.py` — interactive onboarding that asks plain-English questions, validates Telegram live (sends a test message), and writes `.env`. Re-runnable with existing values shown as defaults.

---

## How to Run

```bash
# First time
python3 setup.py

# Normal start
python3 main.py

# Test Telegram without waiting for a real change
python3 main.py --test

# Force re-detect from scratch (wipes baseline)
rm state.json && python3 main.py
```

---

## Known Behaviour

- **First run with existing `state.json`:** If the bot was already running and you restart, it loads the saved baseline and only notifies on *new* changes from that point. To re-notify everything, delete `state.json`.
- **Lunch break (period 5, ~13:05):** Untis returns no lesson object for this slot — it's genuinely empty and never produces a change entry.
- **"details updated" entries:** After the fix, these should only appear for truly unknown field changes (e.g. Untis adds a new field we don't parse yet).
- **AI mode:** If `AI_ENABLED=true` and the model call fails, it automatically falls back to the structured plain-text summary.

---

## What to Build Next

These are ordered roughly by usefulness:

### 1. Daily Morning Summary ⭐ High value
Every day at a configurable time (e.g. 07:00), send a full overview of the day's lessons — subject, teacher, room, time — even if nothing changed. Useful as a daily briefing.

**Where to add it:** `main.py` poll loop — check current time at each cycle start and fire a summary if the hour matches `MORNING_SUMMARY_HOUR` (new `.env` variable). Format with a new `_daily_summary(timetable)` function in `ai.py`.

### 2. Quiet Hours
Don't send notifications between e.g. 22:00 and 07:00. A late Untis update shouldn't wake you up.

**Where to add it:** `notifier.py` — wrap `send()` with a time check. If inside quiet hours, buffer the message and flush it at the quiet-hours end time. Add `QUIET_HOURS_START` / `QUIET_HOURS_END` to `.env` and `config.py`.

### 3. Telegram Bot Commands
Reply to the bot with `/today` or `/tomorrow` to get the current timetable on demand without waiting for a change.

**Where to add it:** New `bot.py` using `python-telegram-bot`'s `Application` class alongside the existing poll loop (run both in separate threads). Commands: `/today`, `/tomorrow`, `/status` (last poll time + health).

### 4. Auto-restart / Run on Startup
Right now the watcher stops if the codespace restarts and you have to `python3 main.py` manually.

**Options:**
- **Codespace:** Add a `.devcontainer/devcontainer.json` `postStartCommand: "python3 main.py &"` to auto-start on codespace open.
- **Linux server:** Create a `systemd` service unit (`untis-watcher.service`) — `ExecStart`, `Restart=always`, `WantedBy=multi-user.target`.
- **Windows:** Add a Task Scheduler entry or use `pythonw.exe` with the tray icon (already supported).

### 5. Smarter "details updated" Diagnosis
Log the full raw before/after diff to a rotating `debug.log` when a change can't be named, so you can inspect what Untis actually sent and improve the formatter over time.

---

## Repo

[https://github.com/aoyn1xw/Untis-watcher](https://github.com/aoyn1xw/Untis-watcher)

Last commits this session:
- `e084138` — fix: detect cancellations hidden inside "changed" entries  
- `92ce062` — feat: add interactive onboarding setup wizard
