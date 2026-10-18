#!/usr/bin/env python3
"""Launch upstream everos-mcp with explicit shared scope and fresh sessions."""
import argparse
import json
import os
from pathlib import Path
import stat
import sys
from configure import validate


def build_env(settings, inherited=None):
    validate(settings)
    # Never let an inherited fixed session or another EverOS scope leak in.
    env = {k: v for k, v in (os.environ if inherited is None else inherited).items()
           if not k.startswith("EVEROS_") and k != "EVER_OS_BASE_URL"}
    for key, field in {
        "EVEROS_API_KEY": "api_key", "EVEROS_BASE_URL": "base_url",
        "EVEROS_USER_ID": "user_id", "EVEROS_APP_ID": "app_id",
        "EVEROS_PROJECT_ID": "project_id", "EVEROS_ASSISTANT_SENDER_ID": "assistant_sender_id",
    }.items():
        env[key] = settings[field]
    # EVEROS_SESSION_ID intentionally omitted: upstream creates one per process.
    return env


def read_settings(path):
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("settings permissions are too open; run chmod 600 on that file")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Validate locally, without network or secret output")
    opts = parser.parse_args()
    settings = read_settings(opts.settings)
    env = build_env(settings)
    if opts.check:
        print(json.dumps({k: settings[k] for k in ("base_url", "user_id", "app_id", "project_id", "assistant_sender_id")}, indent=2))
        print("Settings valid. Fresh session per MCP process. API key omitted.")
        return
    os.environ.clear()
    os.environ.update(env)
    from everos_mcp.server import main as upstream_main
    upstream_main([])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        # Do not echo provider errors or config contents into a client log.
        print(f"Shared-memory launcher: {type(exc).__name__}; check settings and permissions.", file=sys.stderr)
        raise SystemExit(1) from None
