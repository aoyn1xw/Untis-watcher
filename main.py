"""
main.py – Entry point for the untis-watcher bot.

Polls WebUntis every POLL_INTERVAL seconds and sends an AI-generated Telegram
message whenever the timetable changes. Runs in system tray on Windows.
"""

import time
import traceback
import threading
from PIL import Image, ImageDraw
import pystray

import config            # imported early so missing env vars fail fast
import storage
import timetable
import detector
import ai
import notifier


# Global flag to stop the polling loop
running = True


def create_icon_image():
    """Create a simple icon for the system tray."""
    # Create a 64x64 image with a blue circle
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # Draw a circle representing the bot
    draw.ellipse([8, 8, 56, 56], fill='#0088cc', outline='#005580')
    
    # Draw a small indicator dot
    draw.ellipse([44, 12, 52, 20], fill='#00ff00')
    
    return image


def poll_loop() -> None:
    """Main polling loop that checks for timetable changes."""
    global running
    
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
        notifier.send("Untis Watcher is now up and running! I'll notify you of any timetable changes.")
        print("Startup notification sent to Telegram.")
    except Exception as e:
        print(f"Failed to send startup notification: {e}")

    # ── Poll loop ──────────────────────────────────────────────────────────────
    while running:
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

        # Sleep with frequent checks so we can exit quickly
        for _ in range(config.POLL_INTERVAL):
            if not running:
                break
            time.sleep(1)
    
    print("Untis Watcher stopped.")


def on_quit(icon, item):
    """Handle quit action from system tray."""
    global running
    running = False
    icon.stop()


def main() -> None:
    """Set up system tray icon and start polling in background thread."""
    # Start polling in a separate thread
    polling_thread = threading.Thread(target=poll_loop, daemon=True)
    polling_thread.start()
    
    # Create system tray icon
    icon_image = create_icon_image()
    icon = pystray.Icon(
        "untis_watcher",
        icon_image,
        "Untis Watcher",
        menu=pystray.Menu(
            pystray.MenuItem("Untis Watcher is running", lambda: None, enabled=False),
            pystray.MenuItem("Quit", on_quit)
        )
    )
    
    # Run the icon (this blocks until quit is called)
    icon.run()


if __name__ == "__main__":
    main()
