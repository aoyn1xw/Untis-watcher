"""
config.py – Load and expose all configuration from environment variables.
Never import secrets directly; always go through this module.
"""

import os
from dotenv import load_dotenv

# Load variables from a .env file in the project root (if present)
load_dotenv()

# ── WebUntis credentials ──────────────────────────────────────────────────────
UNTIS_SERVER   = os.environ["UNTIS_SERVER"]    # e.g. "melpomene.webuntis.com"
UNTIS_SCHOOL   = os.environ["UNTIS_SCHOOL"]    # school slug as shown in the URL
UNTIS_USER     = os.environ["UNTIS_USER"]
UNTIS_PASSWORD = os.environ["UNTIS_PASSWORD"]

# ── GitHub Models (OpenAI-compatible) ────────────────────────────────────────
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
AI_MODEL     = os.getenv("AI_MODEL", "gpt-4o-mini")

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ── Polling behaviour ─────────────────────────────────────────────────────────
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))   # seconds between polls
DAYS_AHEAD    = int(os.getenv("DAYS_AHEAD", "7"))        # how many days to fetch
