"""
config.py – Load and expose all configuration from environment variables.
Never import secrets directly; always go through this module.
"""

import os
import sys
from dotenv import load_dotenv

# Determine the base path (works for both script and frozen executable)
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    base_path = os.path.dirname(sys.executable)
else:
    # Running as script
    base_path = os.path.dirname(os.path.abspath(__file__))

# Load variables from .env file in the executable/script directory
env_path = os.path.join(base_path, '.env')
load_dotenv(env_path)

# ── WebUntis credentials ──────────────────────────────────────────────────────
UNTIS_SERVER   = os.environ["UNTIS_SERVER"]    # e.g. "melpomene.webuntis.com"
UNTIS_SCHOOL   = os.environ["UNTIS_SCHOOL"]    # school slug as shown in the URL
UNTIS_USER     = os.environ["UNTIS_USER"]
UNTIS_PASSWORD = os.environ["UNTIS_PASSWORD"]
UNTIS_ELEMENT_TYPE = int(os.getenv("UNTIS_ELEMENT_TYPE", "5"))  # 5=class/student
UNTIS_ELEMENT_ID   = int(os.environ["UNTIS_ELEMENT_ID"])        # your class/student ID

# ── GitHub Models (OpenAI-compatible) ────────────────────────────────────────
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
AI_MODEL     = os.getenv("AI_MODEL", "gpt-4o-mini")

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ── Polling behaviour ─────────────────────────────────────────────────────────
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))   # seconds between polls
DAYS_AHEAD    = int(os.getenv("DAYS_AHEAD", "7"))        # how many days to fetch
