"""
main.py – Entry point for the untis-watcher bot.

Polls WebUntis every POLL_INTERVAL seconds and sends an AI-generated Telegram
message whenever the timetable changes.  Errors are printed without crashing the loop.
"""

import time
import traceback

import config            # imported early so missing env vars fail fast
import storage
import timetable
import detector
import ai
import notifier


def main() -> None:
    print("untis-watcher starting up …")

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    last_tt   = storage.load() or []
    last_hash = detector.hash_tt(last_tt)
    is_first_run = len(last_tt) == 0  # Track if this is the first run

    if last_tt:
        print(f"Loaded persisted timetable ({len(last_tt)} lessons).")
    else:
        print("No persisted timetable found – will treat first fetch as baseline.")
    
    # Send startup notification
    try:
        notifier.send("🤖 Untis Watcher is now up and running! I'll notify you of any timetable changes.")
        print("Startup notification sent to Telegram.")
    except Exception as e:
        print(f"Failed to send startup notification: {e}")

    # ── Poll loop ──────────────────────────────────────────────────────────────
    while True:
        try:
            session = timetable.get_session()
            try:
                current_tt   = timetable.fetch(session)
                current_hash = detector.hash_tt(current_tt)

                if current_hash != last_hash and last_hash is not None and not is_first_run:
                    print("[poll] Change detected – analysing …")
                    changes = detector.find_changes(last_tt, current_tt)
                    print(f"       {len(changes)} change(s): "
                          + ", ".join(c["type"] for c in changes))

                    summary = ai.explain(last_tt, current_tt, changes)
                    print(f"       AI summary: {summary[:80]}{'…' if len(summary) > 80 else ''}")

                    notifier.send(summary)
                    print("       Telegram message sent.")
                elif is_first_run:
                    print(f"[poll] First run – saved baseline with {len(current_tt)} lessons.")
                    is_first_run = False  # Only skip once
                else:
                    print(f"[poll] No change detected ({len(current_tt)} lessons).")

                storage.save(current_tt)
                last_tt   = current_tt
                last_hash = current_hash

            finally:
                # Always log out, even if an exception occurred above
                timetable.logout(session)

        except Exception:
            print("[error] Unexpected error during poll:")
            traceback.print_exc()
            # Continue the loop – next poll may succeed

        time.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
    main()
