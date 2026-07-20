"""
main.py – Entry point for the untis-watcher bot.

Polls WebUntis every POLL_INTERVAL seconds and sends a Telegram
message whenever the persisted timetable state changes. Runs in the system tray
on Windows when tray dependencies are available.

Pass --test to send a single fake change notification and exit immediately.
Useful for verifying that Telegram notifications are working correctly.
"""

import argparse
import importlib.util
import logging
import os
import platform
import threading
import time


def _tray_dependencies_available() -> bool:
    has_dependencies = (
        importlib.util.find_spec("PIL") is not None
        and importlib.util.find_spec("pystray") is not None
    )
    has_gui_session = platform.system() == "Windows" or bool(os.environ.get("DISPLAY"))
    return has_dependencies and has_gui_session


_HAS_TRAY = _tray_dependencies_available()

import config
import ai
import detector
import health
import notifier
import storage
import timetable


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("untis-watcher")

_stop_event = threading.Event()

_health = health.HealthMonitor(
    failure_threshold=getattr(config, "FAILURE_ALERT_THRESHOLD", 3),
    heartbeat_interval_s=getattr(config, "HEARTBEAT_INTERVAL", 0),
)

_WATCHDOG_MULTIPLIER = 3


class LoginFailedError(ConnectionError):
    pass


def _sanitize_error(exc: Exception) -> str:
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


def _log_startup_config() -> None:
    """Log active configuration at startup with secrets masked."""
    def _mask(value: str | None, show_chars: int = 4) -> str:
        if not value:
            return "(not set)"
        if len(value) <= show_chars:
            return "****"
        return value[:show_chars] + "****"

    logger.info("[config] Untis server  : %s", config.UNTIS_SERVER or "(not set)")
    logger.info("[config] Untis school  : %s", config.UNTIS_SCHOOL or "(not set)")
    logger.info("[config] Untis user    : %s", config.UNTIS_USER or "(not set)")
    logger.info("[config] Element ID    : %s  type: %s", config.UNTIS_ELEMENT_ID, config.UNTIS_ELEMENT_TYPE)
    logger.info("[config] Days ahead    : %s", config.DAYS_AHEAD)
    logger.info("[config] Poll interval : %ss", config.POLL_INTERVAL)
    logger.info("[config] Telegram token: %s", _mask(config.TELEGRAM_TOKEN))
    logger.info("[config] Telegram chat : %s", config.TELEGRAM_CHAT_ID or "(not set)")
    logger.info("[config] AI enabled    : %s", config.AI_ENABLED)
    if config.AI_ENABLED:
        logger.info("[config] AI model      : %s", config.AI_MODEL or "(not set)")
        logger.info("[config] AI base URL   : %s", config.AI_BASE_URL or "(default OpenAI)")
        logger.info("[config] AI API key    : %s", _mask(config.AI_API_KEY))  # CodeQL[py/clear-text-logging-sensitive-data] - value is masked


def create_icon_image():
    from PIL import Image, ImageDraw
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    draw.ellipse([8, 8, 56, 56], fill='#0088cc', outline='#005580')
    draw.ellipse([44, 12, 52, 20], fill='#00ff00')
    return image


def _send_startup_greeting() -> None:
    try:
        notifier.send("Watcher started. I'm now keeping an eye on your timetable.")
        logger.info("Startup greeting sent via Telegram.")
    except Exception as exc:
        logger.warning("Could not send startup greeting: %s", _sanitize_error(exc))


def _load_previous_timetable() -> list[dict]:
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
    try:
        current_timetable = timetable.fetch(session)
    except Exception:
        logger.exception("Fetch failed; state.json will not be overwritten.")
        raise
    logger.info("Fetch successful with %s lesson(s).", len(current_timetable))
    return current_timetable


def _notify_changes(previous_timetable: list[dict], current_timetable: list[dict], changes: list[dict]) -> None:
    summary = ai.explain(previous_timetable, current_timetable, changes)
    logger.info("Summary generated: %s%s", summary[:80], "…" if len(summary) > 80 else "")
    try:
        notifier.send(summary)
        logger.info("Telegram notification sent.")
    except Exception as exc:
        logger.error("Notification failed: %s", _sanitize_error(exc))


def _process_once(previous_timetable: list[dict]) -> tuple[list[dict], str, int]:
    session = _login_with_retry()
    try:
        current_timetable = _fetch_current_timetable(session)
    finally:
        timetable.logout(session)

    previous_normalised = detector.normalise_timetable(previous_timetable)
    current_normalised = detector.normalise_timetable(current_timetable)

    outcome: str = "ok"
    change_count: int = 0

    if not previous_normalised:
        logger.info("No previous timetable baseline; saving current state without notification.")
    elif previous_normalised != current_normalised:
        changes = detector.find_changes(previous_timetable, current_timetable)
        change_count = len(changes)
        logger.info("Diff detected with %s change(s): %s", change_count, ", ".join(c["type"] for c in changes))
        _notify_changes(previous_timetable, current_timetable, changes)
        outcome = "changed"
    else:
        logger.info("No change detected; normalised timetable matches persisted state.")
        outcome = "no_change"

    storage.save_state(current_timetable)
    logger.info("state.json overwritten with latest fetched data.")
    return current_timetable, outcome, change_count


def run_test_notification() -> None:
    """
    Send a single fake change notification to Telegram and exit.
    Uses a realistic fake lesson so the full notification pipeline is exercised.
    """
    logger.info("[test] Sending fake change notification...")

    fake_before = {
        "id": 9999999,
        "start": "2026-06-12T08:20",
        "end": "2026-06-12T09:05",
        "subjects": ["Mathematik"],
        "teachers": ["JOOS"],
        "rooms": ["B209"],
        "code": None,
        "change_type": "normal",
    }
    fake_after = {
        **fake_before,
        "rooms": ["A101"],
        "code": "irregular",
        "change_type": "changed",
    }
    fake_changes = [
        {
            "type": "changed",
            "lesson": fake_after,
            "before": fake_before,
            "after": fake_after,
        },
        {
            "type": "removed",
            "lesson": {
                "id": 9999998,
                "start": "2026-06-12T10:05",
                "end": "2026-06-12T10:50",
                "subjects": ["Deutsch"],
                "teachers": ["MULL"],
                "rooms": ["C312"],
                "code": "cancelled",
                "change_type": "cancelled",
            },
        },
    ]

    summary = ai.explain([], [], fake_changes)
    logger.info("[test] Summary: %s", summary)
    notifier.send("[TEST] " + summary)
    logger.info("[test] Notification sent. Check your Telegram.")


def poll_loop() -> None:
    logger.info("untis-watcher starting up …")
    _log_startup_config()
    _send_startup_greeting()
    previous_timetable = _load_previous_timetable()

    while not _stop_event.is_set():
        cycle_start = time.time()
        outcome: str = "unknown_error"
        change_count: int = 0
        error_str: str = ""

        try:
            previous_timetable, outcome, change_count = _process_once(previous_timetable)
        except LoginFailedError as exc:
            error_str = _sanitize_error(exc)
            outcome = "login_error"
            logger.exception("Login failed after retry; exiting watcher.")
            _health.record_cycle(
                outcome=outcome,
                latency_s=time.time() - cycle_start,
                error=error_str,
                send_alert_fn=notifier.send,
            )
            _stop_event.set()
            break
        except Exception as exc:
            error_str = _sanitize_error(exc)
            outcome = "fetch_error"
            logger.exception("Unexpected error during watcher cycle; state.json was not overwritten.")
        finally:
            latency = time.time() - cycle_start
            if outcome not in ("login_error",):
                _health.record_cycle(
                    outcome=outcome,
                    latency_s=latency,
                    change_count=change_count,
                    error=error_str,
                    send_alert_fn=notifier.send,
                )

        _health.check_watchdog(
            silence_threshold_s=_WATCHDOG_MULTIPLIER * config.POLL_INTERVAL,
            send_alert_fn=notifier.send,
        )
        _health.maybe_send_heartbeat(send_fn=notifier.send)

        for _ in range(config.POLL_INTERVAL):
            if _stop_event.is_set():
                break
            time.sleep(1)

    logger.info("Untis Watcher stopped.")


def on_quit(icon, item):
    _stop_event.set()
    icon.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Untis Watcher")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a fake change notification to Telegram and exit.",
    )
    args = parser.parse_args()

    if args.test:
        run_test_notification()
        return

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
