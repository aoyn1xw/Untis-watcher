import os
import unittest

# Ensure config import in timetable succeeds
os.environ.setdefault("UNTIS_SERVER", "example.webuntis.com")
os.environ.setdefault("UNTIS_SCHOOL", "example-school")
os.environ.setdefault("UNTIS_USER", "user")
os.environ.setdefault("UNTIS_PASSWORD", "pass")
os.environ.setdefault("UNTIS_ELEMENT_ID", "123")
os.environ.setdefault("GITHUB_TOKEN", "token")
os.environ.setdefault("TELEGRAM_TOKEN", "token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "chat")

import timetable


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self._untis_url = "https://example.webuntis.com/WebUntis/jsonrpc.do?school=example-school"
        self._person_id = 123
        self.post_calls = []

    def post(self, url, json, timeout):
        self.post_calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse(self._payload)


class TimetableTests(unittest.TestCase):
    def test_resolve_change_type_priority(self):
        self.assertEqual(timetable._resolve_change_type("irregular", ["Math Prüfung"]), "exam")
        self.assertEqual(timetable._resolve_change_type("cancelled", ["Math"]), "cancelled")
        self.assertEqual(timetable._resolve_change_type("irregular", ["Math"]), "changed")
        self.assertEqual(timetable._resolve_change_type(None, ["Math"]), "normal")

    def test_fetch_transforms_periods_and_sorts(self):
        payload = {
            "result": [
                {
                    "id": 2,
                    "date": 20260420,
                    "startTime": 930,
                    "endTime": 1015,
                    "su": [{"id": 1, "name": "History"}],
                    "te": [{"id": 10, "name": "AB"}],
                    "ro": [{"id": 20, "name": "R2"}],
                    "code": "irregular",
                },
                {
                    "id": 1,
                    "date": 20260420,
                    "startTime": 800,
                    "endTime": 845,
                    "su": [{"id": 2, "name": "Math Prüfung"}],
                    "te": [{"id": 11, "name": "CD"}],
                    "ro": [{"id": 21, "name": "R1"}],
                    "cellState": "CANCEL",
                },
            ]
        }
        session = FakeSession(payload)

        lessons = timetable.fetch(session)

        self.assertEqual([lesson["id"] for lesson in lessons], [1, 2])
        self.assertEqual(lessons[0]["start"], "2026-04-20T08:00")
        self.assertEqual(lessons[0]["end"], "2026-04-20T08:45")
        self.assertEqual(lessons[0]["subjects"], ["Math Prüfung"])
        self.assertEqual(lessons[0]["change_type"], "exam")  # exam takes priority over cancelled

        self.assertEqual(lessons[1]["change_type"], "changed")
        self.assertEqual(lessons[1]["teachers"], ["AB"])
        self.assertEqual(lessons[1]["rooms"], ["R2"])

        self.assertEqual(len(session.post_calls), 1)


if __name__ == "__main__":
    unittest.main()
