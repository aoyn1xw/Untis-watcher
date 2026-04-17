import tempfile
import unittest
from pathlib import Path
from unittest import mock

import storage


class StorageTests(unittest.TestCase):
    def test_load_returns_none_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "last_timetable.json"
            with mock.patch.object(storage, "_FILE", file_path):
                self.assertIsNone(storage.load())

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "last_timetable.json"
            data = [{"id": 1, "subjects": ["Math"], "start": "2026-04-20T08:00"}]

            with mock.patch.object(storage, "_FILE", file_path):
                storage.save(data)
                loaded = storage.load()

            self.assertEqual(loaded, data)
            self.assertTrue(file_path.exists())


if __name__ == "__main__":
    unittest.main()
