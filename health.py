"""
health.py – Observability layer for untis-watcher.

Tracks:
  - per-cycle structured metrics (timestamp, outcome, latency, change count)
  - consecutive failure counter with configurable alert threshold
  - last-success timestamp for silent-failure / watchdog detection
  - periodic heartbeat Telegram pings (opt-in via HEARTBEAT_INTERVAL env var)

All state is in-memory only; nothing is written to disk.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger("untis-watcher.health")

# Alert after this many consecutive failures (override via config if desired)
DEFAULT_FAILURE_THRESHOLD = 3

Outcome = Literal["ok", "no_change", "changed", "fetch_error", "login_error", "unknown_error"]


@dataclass
class CycleMetric:
    """Structured record for a single watcher cycle."""
    timestamp: float          # unix epoch
    outcome: Outcome
    latency_s: float          # wall-clock seconds for the cycle
    change_count: int = 0     # number of diff items detected
    error: str = ""           # sanitised error string, if any


class HealthMonitor:
    """
    Central observability object.  One instance lives for the process lifetime.

    Usage in main.py::

        health = HealthMonitor(failure_threshold=3)
        health.record_cycle(outcome="ok", latency_s=1.2, change_count=0)
        health.maybe_send_heartbeat(notifier_send_fn)
    """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        heartbeat_interval_s: int = 0,   # 0 = disabled
        max_history: int = 200,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.heartbeat_interval_s = heartbeat_interval_s
        self.max_history = max_history

        self._history: list[CycleMetric] = []
        self._consecutive_failures: int = 0
        self._total_cycles: int = 0
        self._total_errors: int = 0
        self._last_success_ts: float | None = None
        self._last_heartbeat_ts: float = time.time()
        self._alert_sent_at_streak: int = 0   # avoids spamming the same streak

    # ------------------------------------------------------------------
    # Core recording API
    # ------------------------------------------------------------------

    def record_cycle(
        self,
        outcome: Outcome,
        latency_s: float,
        change_count: int = 0,
        error: str = "",
        send_alert_fn=None,   # callable(message: str) – notifier.send
    ) -> None:
        """
        Record the result of one watcher cycle.

        :param outcome:       Semantic result of the cycle.
        :param latency_s:     Wall-clock duration of the cycle in seconds.
        :param change_count:  Number of timetable changes detected (0 for non-diff outcomes).
        :param error:         Sanitised error string (empty string when no error).
        :param send_alert_fn: Optional callable used to send a Telegram alert when the
                              consecutive-failure threshold is crossed.
        """
        metric = CycleMetric(
            timestamp=time.time(),
            outcome=outcome,
            latency_s=round(latency_s, 3),
            change_count=change_count,
            error=error,
        )
        self._history.append(metric)
        if len(self._history) > self.max_history:
            self._history.pop(0)

        self._total_cycles += 1
        is_error = outcome in ("fetch_error", "login_error", "unknown_error")

        if is_error:
            self._consecutive_failures += 1
            self._total_errors += 1
            logger.warning(
                "[health] Failure streak: %s/%s  outcome=%s  error=%s",
                self._consecutive_failures,
                self.failure_threshold,
                outcome,
                error or "(none)",
            )
            self._maybe_send_failure_alert(send_alert_fn)
        else:
            if self._consecutive_failures > 0:
                logger.info(
                    "[health] Recovered after %s consecutive failure(s).",
                    self._consecutive_failures,
                )
            self._consecutive_failures = 0
            self._alert_sent_at_streak = 0
            self._last_success_ts = metric.timestamp

        logger.info(
            "[health] cycle #%s  outcome=%-14s  latency=%.2fs  changes=%s  errors_total=%s",
            self._total_cycles,
            outcome,
            latency_s,
            change_count,
            self._total_errors,
        )

    # ------------------------------------------------------------------
    # Watchdog  (call once per cycle from the poll loop)
    # ------------------------------------------------------------------

    def check_watchdog(
        self,
        silence_threshold_s: float,
        send_alert_fn=None,
    ) -> None:
        """
        Alert if no successful cycle has been recorded for longer than
        *silence_threshold_s* seconds.  Typical value: 3 × POLL_INTERVAL.

        Safe to call even before the first success (no alert fires then).
        """
        if self._last_success_ts is None:
            return   # haven't had a success yet; not a watchdog condition
        silent_for = time.time() - self._last_success_ts
        if silent_for >= silence_threshold_s:
            msg = (
                f"⚠️ Untis Watcher watchdog: no successful cycle for "
                f"{silent_for / 60:.1f} min (threshold {silence_threshold_s / 60:.1f} min)."
            )
            logger.warning("[health] %s", msg)
            if send_alert_fn:
                try:
                    send_alert_fn(msg)
                except Exception:
                    logger.exception("[health] Could not send watchdog alert.")

    # ------------------------------------------------------------------
    # Heartbeat  (call once per cycle from the poll loop)
    # ------------------------------------------------------------------

    def maybe_send_heartbeat(self, send_fn=None) -> None:
        """
        Send a Telegram heartbeat ping if *heartbeat_interval_s* > 0 and the
        interval has elapsed since the last ping.

        Set HEARTBEAT_INTERVAL=3600 in .env to get an hourly "still alive" message.
        Set to 0 (default) to disable entirely.
        """
        if self.heartbeat_interval_s <= 0 or send_fn is None:
            return
        now = time.time()
        if now - self._last_heartbeat_ts < self.heartbeat_interval_s:
            return
        self._last_heartbeat_ts = now
        uptime_min = (now - (self._history[0].timestamp if self._history else now)) / 60
        msg = (
            f"💓 Untis Watcher heartbeat\n"
            f"Cycles: {self._total_cycles} | Errors: {self._total_errors} | "
            f"Streak failures: {self._consecutive_failures} | "
            f"Uptime: {uptime_min:.0f} min"
        )
        logger.info("[health] Sending heartbeat.")
        try:
            send_fn(msg)
        except Exception:
            logger.exception("[health] Could not send heartbeat.")

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return a plain-dict snapshot of current health state."""
        return {
            "total_cycles": self._total_cycles,
            "total_errors": self._total_errors,
            "consecutive_failures": self._consecutive_failures,
            "failure_threshold": self.failure_threshold,
            "last_success_ts": self._last_success_ts,
            "history_length": len(self._history),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_send_failure_alert(self, send_fn=None) -> None:
        """Send a Telegram alert when the consecutive-failure threshold is crossed."""
        if self._consecutive_failures < self.failure_threshold:
            return
        if self._consecutive_failures == self._alert_sent_at_streak:
            return   # already alerted for this exact streak length
        self._alert_sent_at_streak = self._consecutive_failures
        msg = (
            f"🚨 Untis Watcher: {self._consecutive_failures} consecutive fetch failures. "
            f"Check your WebUntis credentials and network connection."
        )
        logger.error("[health] Failure threshold reached (%s); sending alert.", self._consecutive_failures)
        if send_fn:
            try:
                send_fn(msg)
            except Exception:
                logger.exception("[health] Could not send failure alert.")
