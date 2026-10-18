import json
import os
import subprocess
import sys
import tempfile
import unittest

from handoff_brief import build_brief, load_records


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


class BuildBriefTest(unittest.TestCase):
    def test_renders_all_labels_in_input_order(self):
        records = [
            _record(platform="linux", component="relay", check="连通", evidence=[" proof "]),
            _record(platform="nas", component="agent", check="日志", evidence=["", "   "]),
            _record(platform="win", component="client", check="控制", result="failed", evidence=["x"]),
        ]

        self.assertEqual(
            build_brief(records),
            "# uu-remote-linux 验收交接\n"
            "- [有证据] linux / relay / 连通: passed\n"
            "- [待补证] nas / agent / 日志: passed\n"
            "- [未通过] win / client / 控制: failed\n"
            "上线状态：未确认；测试结果不代表已部署。",
        )

    def test_empty_records_still_has_required_boundaries(self):
        self.assertEqual(
            build_brief([]),
            "# uu-remote-linux 验收交接\n上线状态：未确认；测试结果不代表已部署。",
        )

    def test_result_match_is_case_sensitive_and_exact(self):
        records = [_record(result="Passed"), _record(result="passed ")]
        lines = build_brief(records).splitlines()
        self.assertTrue(lines[1].startswith("- [未通过]"))
        self.assertTrue(lines[2].startswith("- [未通过]"))


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.script = os.path.join(os.path.dirname(__file__), "handoff_brief.py")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, self.script, *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def write_json(self, value):
        path = os.path.join(self._tmp.name, "input.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
        return path

    def test_valid_input_with_failed_record_exits_zero(self):
        result = self.run_cli(self.write_json([_record(result="failed", evidence=[])]))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(
            result.stdout,
            "# uu-remote-linux 验收交接\n"
            "- [未通过] nas / agent / connect: failed\n"
            "上线状态：未确认；测试结果不代表已部署。\n",
        )

    def test_invalid_content_exits_two_with_stderr_only(self):
        result = self.run_cli(self.write_json({"records": []}))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("error: "))
        self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_read_error_exits_two_with_stderr_only(self):
        result = self.run_cli(os.path.join(self._tmp.name, "missing.json"))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("error: "))
        self.assertEqual(len(result.stderr.splitlines()), 1)

    def test_argument_error_exits_two_with_stderr_only(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "error: expected one INPUT.json argument\n")


if __name__ == "__main__":
    unittest.main()
