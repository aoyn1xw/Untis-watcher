import unittest

import detector


class DetectorTests(unittest.TestCase):
    def test_hash_ignores_incidental_metadata(self):
        tt_a = [{
            "id": 1,
            "start": "2026-04-20T08:00",
            "end": "2026-04-20T08:45",
            "subjects": ["Math"],
            "teachers": ["AB"],
            "rooms": ["R1"],
            "code": None,
            "change_type": "normal",
        }]
        tt_b = [{
            "id": "1",
            "start": "2026-04-20T08:00",
            "end": "2026-04-20T08:45",
            "subjects": ["Math"],
            "teachers": ["CD"],
            "rooms": ["R2"],
            "code": None,
            "change_type": "normal",
        }]

        self.assertEqual(detector.hash_tt(tt_a), detector.hash_tt(tt_b))

    def test_find_changes_added_removed_changed(self):
        old = [
            {"id": 1, "start": "2026-04-20T08:00", "end": "2026-04-20T08:45", "subjects": ["Math"], "code": None, "change_type": "normal"},
            {"id": 2, "start": "2026-04-20T09:00", "end": "2026-04-20T09:45", "subjects": ["English"], "code": None, "change_type": "normal"},
        ]
        new = [
            {"id": 2, "start": "2026-04-20T09:00", "end": "2026-04-20T09:45", "subjects": ["English Advanced"], "code": "irregular", "change_type": "changed"},
            {"id": 3, "start": "2026-04-20T10:00", "end": "2026-04-20T10:45", "subjects": ["Biology"], "code": None, "change_type": "normal"},
        ]

        changes = detector.find_changes(old, new)
        types = sorted(change["type"] for change in changes)

        self.assertEqual(types, ["added", "changed", "removed"])

    def test_missing_id_uses_stable_matching_for_state_changes(self):
        old = [{
            "id": None,
            "start": "2026-04-20T08:00",
            "end": "2026-04-20T08:45",
            "subjects": ["Math"],
            "code": None,
            "change_type": "normal",
        }]
        new = [{
            "id": None,
            "start": "2026-04-20T08:00",
            "end": "2026-04-20T08:45",
            "subjects": ["Math"],
            "code": "cancelled",
            "change_type": "cancelled",
        }]

        changes = detector.find_changes(old, new)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["type"], "changed")


if __name__ == "__main__":
    unittest.main()
