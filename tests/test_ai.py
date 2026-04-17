import os
import unittest
from unittest import mock

# Ensure config import in ai succeeds
os.environ.setdefault("UNTIS_SERVER", "example.webuntis.com")
os.environ.setdefault("UNTIS_SCHOOL", "example-school")
os.environ.setdefault("UNTIS_USER", "user")
os.environ.setdefault("UNTIS_PASSWORD", "pass")
os.environ.setdefault("UNTIS_ELEMENT_ID", "123")
os.environ.setdefault("GITHUB_TOKEN", "token")
os.environ.setdefault("TELEGRAM_TOKEN", "token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "chat")

import ai


class AIMessage:
    def __init__(self, content):
        self.content = content


class AIChoice:
    def __init__(self, content):
        self.message = AIMessage(content)


class AIResponse:
    def __init__(self, content):
        self.choices = [AIChoice(content)]


class AITests(unittest.TestCase):
    def test_fallback_summary_contains_change_lines(self):
        changes = [{"type": "changed", "lesson": {"subjects": ["Math"], "start": "2026-04-20T08:00", "change_type": "normal"}}]

        text = ai._fallback_summary(changes)

        self.assertIn("Timetable changed (1 change(s))", text)
        self.assertIn("CHANGED: Math at 2026-04-20T08:00", text)

    def test_explain_returns_model_response_on_success(self):
        mock_create = mock.Mock(return_value=AIResponse("  Summary from model  "))
        fake_client = mock.Mock()
        fake_client.chat.completions.create = mock_create

        with mock.patch.object(ai, "_client", fake_client):
            result = ai.explain([], [], [{"type": "added", "lesson": {"subjects": ["Math"]}}])

        self.assertEqual(result, "Summary from model")
        self.assertTrue(mock_create.called)

    def test_explain_uses_fallback_on_exception(self):
        changes = [{"type": "added", "lesson": {"subjects": ["Math"], "start": "2026-04-20T08:00"}}]
        mock_create = mock.Mock(side_effect=RuntimeError("boom"))
        fake_client = mock.Mock()
        fake_client.chat.completions.create = mock_create

        with mock.patch.object(ai, "_client", fake_client), mock.patch.object(ai, "_AI_EXCEPTIONS", (Exception,)):
            result = ai.explain([], [], changes)

        self.assertIn("Timetable changed", result)
        self.assertIn("Math", result)


if __name__ == "__main__":
    unittest.main()
