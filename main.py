"""
main.py – Entry point for the untis-watcher bot.

Polls WebUntis every POLL_INTERVAL seconds and sends an AI-generated Telegram
message whenever the persisted timetable state changes. Runs in the system tray
on Windows when tray dependencies are available.
"""

import importlib.util
import logging
import os
import platform
import threading
import time


def _tray_dependencies_available() -> bool:
    """Return whether system-tray dependencies and a GUI session appear available."""
    has_dependencies = (
        importlib.util.find_spec("PIL") is not None
        and importlib.util.find_spec("pystray") is not None
    )
    has_gui_session = platform.system() == "Windows" or bool(os.environ.get("DISPLAY"))
    return has_dependencies and has_gui_session


_HAS_TRAY = _tray_dependencies_available()

import config            # imported early so missing env vars fail fast
import ai
import detector
import notifier
import storage
import timetable


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("untis-watcher")

# Global flag to stop the polling loop
running = True


class LoginFailedError(ConnectionError):
    """Raised when WebUntis login fails after the retry attempt."""


def _sanitize_error(exc: Exception) -> str:
    """
    Return a safe string representation of an exception.
    Replaces any occurrence of sensitive config values (tokens, passwords)
    with redacted placeholders so they never appear in logs.
    """
    msg = str(exc)
    sensitive = [
        (config.TELEGRAM_TOKEN, "<TELEGRAM_TOKEN>"),
        (config.UNTIS_PASSWORD, "<UNTIS_PASSWORD>"),
        (config.AI_API_KEY,     "<AI_API_KEY>"),
    ]
    for secret, placeholder in sensitive:
        if secret and secret in msg:
            msg = msg.replace(secret, placeholder)
    return msg


def create_icon_image():
    """Create a simple icon for the system tray."""
    from PIL import Image, ImageDraw

    width = 64
    height = 64
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)

    draw.ellipse([8, 8, 56, 56], fill='#0088cc', outline='#005580')
    draw.ellipse([44, 12, 52, 20], fill='#00ff00')

    return image


def _send_startup_greeting() -> None:
    """Send a startup message to Telegram. Failures are non-fatal."""
    try:
        notifier.send("Watcher started. I'm now keeping an eye on your timetable.")
        logger.info("Startup greeting sent via Telegram.")
    except Exception as exc:
        logger.warning("Could not send startup greeting: %s", _sanitize_error(exc))


def _load_previous_timetable() -> list[dict]:
    """Load the previous persisted state from state.json, if it exists."""
    state = storage.load_state()
    if not state:
        logger.info("No state.json found; first successful fetch will become the baseline.")
        return []

    previous_timetable = state.get("timetable")
    if not isinstance(previous_timetable, list):
        logger.warning("state.json did not contain a timetable list; starting with an empty baseline.")
        return []

    normalised_count = len(detector.normalise_timetable(previous_timetable))
    logger.info("Loaded state.json baseline with %s normalised lesson(s).", normalised_count)
    return previous_timetable


def _login_with_retry() -> object:
    """Log in to WebUntis, retrying once before surfacing a fatal login error."""
    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            session = timetable.get_session()
            logger.info("Login successful on attempt %s.", attempt)
            return session
        except Exception as exc:
            last_error = exc
            logger.warning("Login failed on attempt %s/2: %s", attempt, _sanitize_error(exc))
            if attempt == 1:
                time.sleep(2)

    raise LoginFailedError("WebUntis login failed after 2 attempts.") from last_error


def _fetch_current_timetable(session: object) -> list[dict]:
    """Fetch the latest WebUntis timetable and log the result."""
    try:
        current_timetable = timetable.fetch(session)
    except Exception:
        logger.exception("Fetch failed; state.json will not be overwritten.")
        raise

    logger.info("Fetch successful with %s lesson(s).", len(current_timetable))
    return current_timetable


def _notify_changes(previous_timetable: list[dict], current_timetable: list[dict], changes: list[dict]) -> None:
    """Generate and send the existing timetable-change notification."""
    summary = ai.explain(previous_timetable, current_timetable, changes)
    logger.info("AI summary generated: %s%s", summary[:80], "…" if len(summary) > 80 else "")

    try:
        notifier.send(summary)
        logger.info("Telegram notification sent.")
    except Exception as exc:
        logger.error("Notification failed: %s", _sanitize_error(exc))


def _process_once(previous_timetable: list[dict]) -> list[dict]:
    """
    Run one stateful watcher cycle.

    The state file is overwritten only after a successful fetch. Fetch failures
    leave the previous state on disk untouched so failed polls do not cause false
    positives or duplicate notifications on the next run.
    """
    session = _login_with_retry()
    try:
        current_timetable = _fetch_current_timetable(session)
    finally:
        timetable.logout(session)

    previous_normalised = detector.normalise_timetable(previous_timetable)
    current_normalised = detector.normalise_timetable(current_timetable)

    if not previous_normalised:
        logger.info("No previous timetable baseline; saving current state without notification.")
    elif previous_normalised != current_normalised:
        changes = detector.find_changes(previous_timetable, current_timetable)
        logger.info("Diff detected with %s change(s): %s", len(changes), ", ".join(c["type"] for c in changes))
        _notify_changes(previous_timetable, current_timetable, changes)
    else:
        logger.info("No change detected; normalised timetable matches persisted state.")

    storage.save_state(current_timetable)
    logger.info("state.json overwritten with latest fetched data.")
    return current_timetable


def poll_loop() -> None:
    """Main watcher loop that checks for timetable changes against state.json."""
    global running

    logger.info("untis-watcher starting up …")
    _send_startup_greeting()
    previous_timetable = _load_previous_timetable()

    while running:
        try:
            previous_timetable = _process_once(previous_timetable)
        except LoginFailedError:
            logger.exception("Login failed after retry; exiting watcher.")
            running = False
            break
        except Exception:
            logger.exception("Unexpected error during watcher cycle; state.json was not overwritten.")

        for _ in range(config.POLL_INTERVAL):
            if not running:
                break
            time.sleep(1)

    logger.info("Untis Watcher stopped.")


def on_quit(icon, item):
    """Handle quit action from system tray."""
    global running
    running = False
    icon.stop()


def main() -> None:
    """Run with tray support when available, otherwise run in headless mode."""
    if _HAS_TRAY:
        import pystray

        polling_thread = threading.Thread(target=poll_loop, daemon=True)
        polling_thread.start()

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

        icon.run()
    else:
        logger.info("pystray/Pillow not available – running in headless mode.")
        poll_loop()


if __name__ == "__main__":
    main()
