"""
selftest.py – Verify that all three integrations are working before relying on
the watcher in production.

Run with:
    python selftest.py

Checks performed:
  1. Telegram  – sends a real test message to your configured chat
  2. AI        – calls the configured OpenAI-compatible endpoint with a fake change
  3. Untis     – logs in, fetches the timetable, and immediately logs out

Each check prints PASS or FAIL with a short reason. No state.json is touched.
"""

import sys

# ── helpers ──────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

_results: list[tuple[str, bool, str]] = []


def _ok(label: str, detail: str = "") -> None:
    _results.append((label, True, detail))
    suffix = f"  ({detail})" if detail else ""
    print(f"  {GREEN}✓ PASS{RESET}  {label}{suffix}")


def _fail(label: str, reason: str) -> None:
    _results.append((label, False, reason))
    print(f"  {RED}✗ FAIL{RESET}  {label}  →  {reason}")


# ── individual checks ─────────────────────────────────────────────────────────

def check_telegram() -> None:
    print(f"\n{YELLOW}[1/3] Telegram{RESET}")
    try:
        from notifier import send
        send("🧪 Untis Watcher self-test: Telegram is working correctly.")
        _ok("Telegram", "message sent – check your chat")
    except Exception as exc:
        _fail("Telegram", str(exc))


def check_ai() -> None:
    print(f"\n{YELLOW}[2/3] AI endpoint{RESET}")
    try:
        from config import AI_BASE_URL, AI_MODEL
        from ai import explain, _structured_summary

        fake_changes = [
            {
                "type": "cancelled",
                "lesson": {
                    "subjects": ["Math"],
                    "start": "08:00",
                    "change_type": "cancelled",
                },
            }
        ]

        result = explain([], [], fake_changes)
        fallback = _structured_summary(fake_changes)

        if result == fallback:
            # explain() returned the plain-text fallback, meaning the API call failed
            _fail(
                "AI endpoint",
                "got plain-text fallback – API call likely failed (check AI_API_KEY / AI_BASE_URL)",
            )
        else:
            endpoint = AI_BASE_URL or "api.openai.com (default)"
            _ok("AI endpoint", f"model={AI_MODEL}  endpoint={endpoint}")
            print(f"       Preview: {result[:120].strip()}{'…' if len(result) > 120 else ''}")
    except Exception as exc:
        _fail("AI endpoint", str(exc))


def check_untis() -> None:
    print(f"\n{YELLOW}[3/3] WebUntis{RESET}")
    try:
        import timetable

        session = timetable.get_session()
        lessons = timetable.fetch(session)
        timetable.logout(session)
        _ok("WebUntis login", "login + logout successful")
        _ok("WebUntis fetch", f"{len(lessons)} lesson(s) fetched")
    except Exception as exc:
        _fail("WebUntis", str(exc))


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 52)
    print("  Untis Watcher – self-test")
    print("=" * 52)

    check_telegram()
    check_ai()
    check_untis()

    # ── summary ──────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in _results if ok)
    total  = len(_results)
    failed = [label for label, ok, _ in _results if not ok]

    print("\n" + "=" * 52)
    if failed:
        print(f"  {RED}Result: {passed}/{total} checks passed{RESET}")
        print(f"  Failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"  {GREEN}Result: all {total} checks passed ✓{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
