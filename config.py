"""
config.py – Load and expose all configuration from environment variables.
Never import secrets directly; always go through this module.
"""

import os
import sys
from dotenv import load_dotenv

# Determine the base path (works for both script and frozen executable)
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

# Load variables from .env file in the executable/script directory
env_path = os.path.join(base_path, '.env')
load_dotenv(env_path)

# ── WebUntis credentials ────────────────────────────────────────────────────────────────────
UNTIS_SERVER   = os.environ["UNTIS_SERVER"]    # e.g. "melpomene.webuntis.com"
UNTIS_SCHOOL   = os.environ["UNTIS_SCHOOL"]    # school slug as shown in the URL
UNTIS_USER     = os.environ["UNTIS_USER"]
UNTIS_PASSWORD = os.environ["UNTIS_PASSWORD"]
UNTIS_ELEMENT_TYPE = int(os.getenv("UNTIS_ELEMENT_TYPE", "5"))  # 5=class/student
UNTIS_ELEMENT_ID   = int(os.environ["UNTIS_ELEMENT_ID"])        # your class/student ID
UNTIS_TENANT_ID    = os.getenv("UNTIS_TENANT_ID")
UNTIS_CLIENT_ID    = os.getenv("UNTIS_CLIENT_ID")
UNTIS_API_PASSWORD = os.getenv("UNTIS_API_PASSWORD")

# ── AI / OpenAI-compatible endpoint ──────────────────────────────────────────────────
# AI_ENABLED:  set to "false" to skip the AI model entirely and always use
#              the structured plain-text summary built from raw Untis data.
#              Defaults to "true" when AI_API_KEY is present, "false" when not.
#
# AI_API_KEY:  your API key for the chosen endpoint.
#              Falls back to GITHUB_TOKEN for backwards compatibility with the
#              old GitHub Models setup.
# AI_BASE_URL: optional custom base URL for any OpenAI-compatible endpoint.
#              Leave unset to use the default OpenAI API (api.openai.com).
#
# Examples:
#   OpenAI:          AI_API_KEY=sk-...          (no AI_BASE_URL needed)
#   GitHub Models:   AI_API_KEY=<github token>  AI_BASE_URL=https://models.github.ai/inference
#   LM Studio:       AI_API_KEY=lm-studio       AI_BASE_URL=http://localhost:1234/v1
#   Ollama:          AI_API_KEY=ollama          AI_BASE_URL=http://localhost:11434/v1
#   Together AI:     AI_API_KEY=<together key>  AI_BASE_URL=https://api.together.xyz/v1
AI_API_KEY  = os.getenv("AI_API_KEY") or os.getenv("GITHUB_TOKEN", "")
AI_BASE_URL = os.getenv("AI_BASE_URL")   # None = use OpenAI default
AI_MODEL    = os.getenv("AI_MODEL", "gpt-4o-mini")

# AI is enabled only when explicitly set to "true", OR when not set at all but
# an API key is present. Set AI_ENABLED=false to force plain-text mode.
_ai_enabled_env = os.getenv("AI_ENABLED", "").strip().lower()
if _ai_enabled_env == "false":
    AI_ENABLED = False
elif _ai_enabled_env == "true":
    AI_ENABLED = True
else:
    # Auto-detect: enabled only when a key is actually configured
    AI_ENABLED = bool(AI_API_KEY)

# ── Telegram ───────────────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# ── Polling behaviour ────────────────────────────────────────────────────────────────────────
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))   # seconds between polls
DAYS_AHEAD    = int(os.getenv("DAYS_AHEAD", "7"))        # how many days to fetch
