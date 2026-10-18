#!/usr/bin/env python3
"""Generate local configuration snippets. Never edits either client's settings."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"[A-Za-z0-9_.@+-]{1,100}\Z")


def validate(settings):
    for name in ("user_id", "app_id", "project_id", "assistant_sender_id"):
        value = settings.get(name, "")
        if not isinstance(value, str) or not ID.fullmatch(value) or value in (".", ".."):
            raise ValueError(f"{name}: use 1–100 letters, digits or _ . @ + -")
    parsed = urlsplit(settings.get("base_url", ""))
    if (parsed.scheme not in ("https", "http") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("base_url must be an http(s) origin without credentials, path or query")
    if not isinstance(settings.get("api_key"), str):
        raise ValueError("api_key must be a string")
    if parsed.hostname == "evermind.ai" or parsed.hostname.endswith(".evermind.ai"):
        if not settings["api_key"].strip():
            raise ValueError("Cloud requires an API key")
    return settings


def render(settings_path, python=sys.executable):
    # Keep the virtualenv executable path; resolve() follows its symlink to
    # the base Python, which loses the virtualenv's installed packages.
    command = os.path.abspath(python)
    args = [str(ROOT / "scripts" / "serve.py"), "--settings", str(settings_path.resolve())]
    claude = {"mcpServers": {"everos-shared": {"command": command, "args": args}}}
    # JSON strings are valid TOML basic strings, including escaped Windows paths.
    toml = ("[mcp_servers.everos-shared]\ncommand = " + json.dumps(command)
            + "\nargs = " + json.dumps(args) + "\nstartup_timeout_sec = 30\ntool_timeout_sec = 240\n")
    return claude, toml


def private_write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".local")
    parser.add_argument("--user", required=True, help="Your own identity; do not use another person's ID")
    parser.add_argument("--project", required=True)
    parser.add_argument("--app", default="shared-memory")
    parser.add_argument("--agent", help="Same value in both clients pools agent experience")
    parser.add_argument("--base-url", default="https://api.evermind.ai")
    parser.add_argument("--no-key", action="store_true", help="Self-hosted origin only")
    opts = parser.parse_args()
    key = "" if opts.no_key else os.environ.get("EVEROS_API_KEY", "").strip()
    if not opts.no_key and not key:
        key = getpass.getpass("EverOS API key (hidden): ").strip()
    settings = validate(dict(api_key=key, base_url=opts.base_url.rstrip("/"), user_id=opts.user,
                             app_id=opts.app, project_id=opts.project,
                             assistant_sender_id=opts.agent or "assistant-" + opts.user))
    output = opts.output.resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths = [output / n for n in ("settings.json", "claude.mcp.json", "codex.mcp.toml")]
    if any(p.exists() for p in paths):
        raise SystemExit("Output files already exist; choose another --output. Nothing overwritten.")
    claude, toml = render(paths[0])
    private_write(paths[0], json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    private_write(paths[1], json.dumps(claude, ensure_ascii=False, indent=2) + "\n")
    private_write(paths[2], toml)
    print("Generated local files (API key not printed):")
    for path in paths:
        print(path)
    print("Merge the MCP entries into each client's configuration; see README.md.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Configuration error: {exc}") from None
