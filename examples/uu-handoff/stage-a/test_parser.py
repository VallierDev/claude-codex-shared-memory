import json
import os
import tempfile
import unittest

from handoff_brief import load_records


def _record(**overrides):
    record = {
        "component": "agent",
        "platform": "nas",
        "check": "connect",
        "result": "passed",
        "evidence": ["log.txt"],
    }
    record.update(overrides)
    return record


class LoadRecordsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def write_bytes(self, data):
        path = os.path.join(self._tmp.name, "input.json")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def write_json(self, value):
        return self.write_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def test_valid_records_keep_order_and_extra_fields(self):
        records = [
            _record(component="甲", note="extra", id=1),
            _record(component="乙", result="failed", evidence=[]),
            _record(component="丙"),
        ]
        loaded = load_records(self.write_json(records))
        self.assertEqual(loaded, records)
        self.assertEqual([r["component"] for r in loaded], ["甲", "乙", "丙"])
        self.assertEqual(loaded[0]["note"], "extra")

    def test_empty_array(self):
        self.assertEqual(load_records(self.write_json([])), [])

    def test_empty_evidence_allowed(self):
        loaded = load_records(self.write_json([_record(evidence=[])]))
        self.assertEqual(loaded[0]["evidence"], [])

    def test_top_level_not_array(self):
        with self.assertRaises(ValueError):
            load_records(self.write_json({"records": []}))

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            load_records(self.write_bytes(b"[{"))

    def test_invalid_utf8(self):
        with self.assertRaises(ValueError):
            load_records(self.write_bytes(b'["\xff"]'))

    def test_record_not_object(self):
        with self.assertRaises(ValueError):
            load_records(self.write_json(["oops"]))

    def test_required_fields(self):
        for field in ("component", "platform", "check", "result"):
            for bad in (None, "", "   ", 1, ["x"]):
                with self.subTest(field=field, bad=bad):
                    record = _record(**{field: bad})
                    with self.assertRaises(ValueError):
                        load_records(self.write_json([record]))
            with self.subTest(field=field, missing=True):
                record = _record()
                del record[field]
                with self.assertRaises(ValueError):
                    load_records(self.write_json([record]))

    def test_evidence_must_be_string_array(self):
        for bad in (None, "log.txt", {"a": 1}, [1], ["ok", None]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    load_records(self.write_json([_record(evidence=bad)]))
        record = _record()
        del record["evidence"]
        with self.assertRaises(ValueError):
            load_records(self.write_json([record]))

    def test_missing_file_raises_oserror(self):
        missing = os.path.join(self._tmp.name, "missing.json")
        with self.assertRaises(OSError):
            load_records(missing)


if __name__ == "__main__":
    unittest.main()
