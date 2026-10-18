"""Parse and render test records for uu-remote-linux handoff briefs."""

import json
import sys

REQUIRED_STRING_FIELDS = ("component", "platform", "check", "result")


def _validate_record(index, record):
    if not isinstance(record, dict):
        raise ValueError(f"record {index}: expected an object")
    for field in REQUIRED_STRING_FIELDS:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"record {index}: '{field}' must be a non-empty string")
    evidence = record.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError(f"record {index}: 'evidence' must be an array of strings")
    for item in evidence:
        if not isinstance(item, str):
            raise ValueError(f"record {index}: 'evidence' must be an array of strings")


def load_records(path):
    """Load and validate records from a UTF-8 JSON array file.

    Returns the records as dicts in input order, extra fields preserved.
    Raises ValueError for invalid content; OSError from reading propagates.
    """
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"input is not valid UTF-8: {exc}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from None
    if not isinstance(data, list):
        raise ValueError("top-level JSON value must be an array")
    for index, record in enumerate(data):
        _validate_record(index, record)
    return data


def build_brief(records):
    """Render validated records as a Markdown handoff brief."""
    lines = ["# uu-remote-linux 验收交接"]
    for record in records:
        has_evidence = any(item.strip() for item in record["evidence"])
        if record["result"] == "passed":
            label = "有证据" if has_evidence else "待补证"
        else:
            label = "未通过"
        lines.append(
            f"- [{label}] {record['platform']} / {record['component']} / "
            f"{record['check']}: {record['result']}"
        )
    lines.append("上线状态：未确认；测试结果不代表已部署。")
    return "\n".join(lines)


def main(argv=None):
    """Run the handoff brief command-line interface."""
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) != 1:
        print("error: expected one INPUT.json argument", file=sys.stderr)
        return 2
    try:
        records = load_records(argv[0])
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(build_brief(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
