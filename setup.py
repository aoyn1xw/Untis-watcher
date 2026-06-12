"""
setup.py – Interactive onboarding wizard for Untis Watcher.

Walks the user through every required setting with plain-English prompts,
validates Telegram credentials live, and writes a .env file.

Run:
    python3 setup.py
Re-run any time to update settings (existing values shown as defaults).
"""

import asyncio
import os
import re
import sys

# ── helpers ───────────────────────────────────────────────────────────────────

BOLD  = "\033[1m"
GREEN = "\033[32m"
CYAN  = "\033[36m"
YELLOW = "\033[33m"
RED   = "\033[31m"
RESET = "\033[0m"
DIM   = "\033[2m"

def _h(text: str) -> str:
    return f"{BOLD}{CYAN}{text}{RESET}"

def _ok(text: str) -> str:
    return f"{GREEN}✅ {text}{RESET}"

def _warn(text: str) -> str:
    return f"{YELLOW}⚠️  {text}{RESET}"

def _err(text: str) -> str:
    return f"{RED}❌ {text}{RESET}"

def _dim(text: str) -> str:
    return f"{DIM}{text}{RESET}"


def _load_existing_env(path: str) -> dict:
    """Parse an existing .env file into a dict (no value overrides os.environ)."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _ask(prompt: str, default: str = "", secret: bool = False, hint: str = "") -> str:
    """
    Show a question and return the user's answer.
    If the user presses Enter without typing, `default` is returned.
    """
    if hint:
        print(f"  {_dim(hint)}")

    default_display = f"[{_dim(default)}] " if default else ""

    if secret and default:
        default_display = f"[{_dim('****')}] "

    while True:
        try:
            if secret:
                import getpass
                answer = getpass.getpass(f"  {BOLD}{prompt}{RESET} {default_display}: ").strip()
            else:
                answer = input(f"  {BOLD}{prompt}{RESET} {default_display}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nSetup cancelled.")
            sys.exit(0)

        if not answer and default:
            return default
        if answer:
            return answer
        print(f"  {_warn('This field is required.')}")


def _ask_optional(prompt: str, default: str = "", hint: str = "") -> str:
    """Like _ask but allows empty input (returns empty string or default)."""
    if hint:
        print(f"  {_dim(hint)}")
    default_display = f"[{_dim(default or 'skip')}] "
    try:
        answer = input(f"  {BOLD}{prompt}{RESET} {default_display}: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n\nSetup cancelled.")
        sys.exit(0)
    return answer if answer else default


def _clean_server(raw: str) -> str:
    """Strip protocol and path from a server URL, keep only the hostname."""
    raw = raw.strip().rstrip("/")
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.split("/")[0]
    return raw


# ── validation ────────────────────────────────────────────────────────────────

async def _check_telegram(token: str, chat_id: str) -> tuple[bool, str]:
    """Returns (success, message)."""
    try:
        from telegram import Bot
        from telegram.error import TelegramError
    except ImportError:
        return False, "python-telegram-bot not installed (run: pip install python-telegram-bot)"

    try:
        bot = Bot(token=token)
        me = await bot.get_me()
        bot_name = f"@{me.username}"

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "👋 Untis Watcher setup complete!\n"
                "This bot will notify you when your timetable changes."
            ),
        )
        return True, f"Bot found: {bot_name} — test message sent!"
    except Exception as exc:
        return False, str(exc)


def _validate_telegram(token: str, chat_id: str) -> bool:
    print(f"  {_dim('Testing Telegram connection...')}", end="", flush=True)
    ok, msg = asyncio.run(_check_telegram(token, chat_id))
    if ok:
        print(f"\r  {_ok(msg)}")
    else:
        print(f"\r  {_err(msg)}")
    return ok


# ── sections ──────────────────────────────────────────────────────────────────

def section_untis(existing: dict) -> dict:
    print(f"\n{_h('── 1 / 4  WebUntis credentials ──────────────────────────')}\n")

    server_raw = _ask(
        "What is your Untis server?",
        default=existing.get("UNTIS_SERVER", ""),
        hint="Open WebUntis in your browser and copy the hostname, e.g. heiken.webuntis.com",
    )
    server = _clean_server(server_raw)
    if server != server_raw.strip():
        print(f"  {_dim(f'→ Using hostname: {server}')}")

    school = _ask(
        "What is your school slug?",
        default=existing.get("UNTIS_SCHOOL", ""),
        hint="It's the part after /school/ in the URL, e.g. gesamtschule-uellendahl",
    )

    user = _ask(
        "What is your Untis username?",
        default=existing.get("UNTIS_USER", ""),
    )

    password = _ask(
        "What is your Untis password?",
        default=existing.get("UNTIS_PASSWORD", ""),
        secret=True,
    )

    element_id = _ask(
        "What is your Untis element ID (student/class ID)?",
        default=existing.get("UNTIS_ELEMENT_ID", ""),
        hint="You can find this in the URL when viewing your timetable, e.g. ...?elementId=12345",
    )

    element_type = _ask_optional(
        "Element type?",
        default=existing.get("UNTIS_ELEMENT_TYPE", "5"),
        hint="5 = student (default), leave blank to keep current",
    ) or "5"

    return {
        "UNTIS_SERVER": server,
        "UNTIS_SCHOOL": school,
        "UNTIS_USER": user,
        "UNTIS_PASSWORD": password,
        "UNTIS_ELEMENT_ID": element_id,
        "UNTIS_ELEMENT_TYPE": element_type,
    }


def section_telegram(existing: dict) -> dict:
    print(f"\n{_h('── 2 / 4  Telegram notifications ────────────────────────')}\n")

    print(f"  {_dim('Need a bot token? Message @BotFather on Telegram and type /newbot')}\n")

    while True:
        token = _ask(
            "What is your Telegram bot token?",
            default=existing.get("TELEGRAM_TOKEN", ""),
            secret=True,
        )

        print(f"  {_dim('Need your chat ID? Start a conversation with your bot, then run:')}")
        print(f"  {_dim('  curl https://api.telegram.org/bot<TOKEN>/getUpdates')}\n")

        chat_id = _ask(
            "What is your Telegram chat ID?",
            default=existing.get("TELEGRAM_CHAT_ID", ""),
            hint="A number like 123456789 (or negative for a group: -100123456789)",
        )

        if _validate_telegram(token, chat_id):
            break
        retry = input(f"\n  Try again? (Y/n): ").strip().lower()
        if retry == "n":
            print(f"  {_warn('Continuing anyway — check your token and chat ID later.')}")
            break

    return {
        "TELEGRAM_TOKEN": token,
        "TELEGRAM_CHAT_ID": chat_id,
    }


def section_ai(existing: dict) -> dict:
    print(f"\n{_h('── 3 / 4  AI summaries (optional) ───────────────────────')}\n")
    print(f"  {_dim('AI writes friendly plain-English change summaries.')}")
    print(f"  {_dim('Works with NVIDIA NIM, OpenAI, GitHub Models, Ollama, etc.')}")
    print(f"  {_dim('Press Enter to skip and use the built-in structured summary.\n')}")

    api_key = _ask_optional(
        "AI API key?",
        default=existing.get("AI_API_KEY", ""),
    )

    if not api_key:
        print(f"  {_dim('→ Skipping AI — structured summary will be used.')}")
        return {"AI_ENABLED": "false", "AI_API_KEY": "", "AI_BASE_URL": "", "AI_MODEL": ""}

    base_url = _ask_optional(
        "AI base URL?",
        default=existing.get("AI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        hint="e.g. https://integrate.api.nvidia.com/v1  or  https://api.openai.com/v1",
    )

    model = _ask_optional(
        "AI model name?",
        default=existing.get("AI_MODEL", "google/gemma-4-31b-it"),
        hint="e.g. google/gemma-4-31b-it  or  gpt-4o-mini",
    )

    return {
        "AI_ENABLED": "true",
        "AI_API_KEY": api_key,
        "AI_BASE_URL": base_url,
        "AI_MODEL": model,
    }


def section_polling(existing: dict) -> dict:
    print(f"\n{_h('── 4 / 4  Polling interval ───────────────────────────────')}\n")

    interval = _ask_optional(
        "How often should it check for changes? (seconds)",
        default=existing.get("POLL_INTERVAL", "300"),
        hint="300 = every 5 minutes (recommended). Minimum: 30",
    ) or "300"

    try:
        interval_int = max(30, int(interval))
    except ValueError:
        interval_int = 300
    interval = str(interval_int)

    days = _ask_optional(
        "How many days ahead should it fetch?",
        default=existing.get("DAYS_AHEAD", "7"),
        hint="7 = one week ahead (recommended)",
    ) or "7"

    return {
        "POLL_INTERVAL": interval,
        "DAYS_AHEAD": days,
    }


# ── write .env ────────────────────────────────────────────────────────────────

def write_env(path: str, values: dict) -> None:
    lines = [
        "# Untis Watcher configuration",
        "# Generated by setup.py — re-run to update",
        "",
        "# ── WebUntis ──",
        f'UNTIS_SERVER={values.get("UNTIS_SERVER", "")}',
        f'UNTIS_SCHOOL={values.get("UNTIS_SCHOOL", "")}',
        f'UNTIS_USER={values.get("UNTIS_USER", "")}',
        f'UNTIS_PASSWORD={values.get("UNTIS_PASSWORD", "")}',
        f'UNTIS_ELEMENT_ID={values.get("UNTIS_ELEMENT_ID", "")}',
        f'UNTIS_ELEMENT_TYPE={values.get("UNTIS_ELEMENT_TYPE", "5")}',
        "",
        "# ── Telegram ──",
        f'TELEGRAM_TOKEN={values.get("TELEGRAM_TOKEN", "")}',
        f'TELEGRAM_CHAT_ID={values.get("TELEGRAM_CHAT_ID", "")}',
        "",
        "# ── AI ──",
        f'AI_ENABLED={values.get("AI_ENABLED", "false")}',
        f'AI_API_KEY={values.get("AI_API_KEY", "")}',
        f'AI_BASE_URL={values.get("AI_BASE_URL", "")}',
        f'AI_MODEL={values.get("AI_MODEL", "")}',
        "",
        "# ── Polling ──",
        f'POLL_INTERVAL={values.get("POLL_INTERVAL", "300")}',
        f'DAYS_AHEAD={values.get("DAYS_AHEAD", "7")}',
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    existing = _load_existing_env(env_path)

    is_rerun = bool(existing)

    print(f"""
{BOLD}{CYAN}╔══════════════════════════════════════════╗
║        🎓  Untis Watcher Setup          ║
╚══════════════════════════════════════════╝{RESET}""")

    if is_rerun:
        print(f"  {_dim('Existing .env found — press Enter to keep current values.')}")

    config: dict = {}
    config.update(section_untis(existing))
    config.update(section_telegram(existing))
    config.update(section_ai(existing))
    config.update(section_polling(existing))

    write_env(env_path, config)

    print(f"""
{_ok(f'.env written to {env_path}')}

  {BOLD}You're all set! Start the watcher with:{RESET}
  {CYAN}python3 main.py{RESET}

  {_dim('Or test notifications right now:')}
  {CYAN}python3 main.py --test{RESET}
""")


if __name__ == "__main__":
    main()
