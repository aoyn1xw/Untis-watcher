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

    if last_tt:
        print(f"Loaded persisted timetable ({len(last_tt)} lessons).")
    else:
        print("No persisted timetable found – will treat first fetch as baseline.")

    # ── Poll loop ──────────────────────────────────────────────────────────────
    while True:
        try:
            session = timetable.get_session()
            try:
                current_tt   = timetable.fetch(session)
                current_hash = detector.hash_tt(current_tt)

                if current_hash == last_hash:
                    print(f"[poll] No change detected ({len(current_tt)} lessons).")
                else:
                    print("[poll] Change detected – analysing …")
                    changes = detector.find_changes(last_tt, current_tt)
                    print(f"       {len(changes)} change(s): "
                          + ", ".join(c["type"] for c in changes))

                    summary = ai.explain(last_tt, current_tt, changes)
                    print(f"       AI summary: {summary[:80]}{'…' if len(summary) > 80 else ''}")

                    notifier.send(summary)
                    print("       Telegram message sent.")

                    storage.save(current_tt)
                    last_tt   = current_tt
                    last_hash = current_hash

            finally:
                # Always log out, even if an exception occurred above
                session.logout()

        except Exception:
            print("[error] Unexpected error during poll:")
            traceback.print_exc()
            # Continue the loop – next poll may succeed

        time.sleep(config.POLL_INTERVAL)


if __name__ == "__main__":
    main()
