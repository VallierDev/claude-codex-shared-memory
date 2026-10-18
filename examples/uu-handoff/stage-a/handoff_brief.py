"""Parse test records for uu-remote-linux handoff briefs."""

import json

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
