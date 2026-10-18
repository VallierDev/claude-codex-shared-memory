#!/usr/bin/env python3
"""Opt-in live MCP write/read between two independent server processes."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
import time
import uuid
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def text(result):
    return "\n".join(getattr(c, "text", "") for c in result.content)


@asynccontextmanager
async def connection(settings):
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "scripts/serve.py"), "--settings", str(settings.resolve())], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            yield client


async def run(settings, timeout):
    marker = "handoff-check-" + uuid.uuid4().hex[:10]
    result = {"marker": marker, "test": "Two MCP processes, not two real model clients", "written": False, "retrieved": False}
    async with connection(settings) as writer:
        tools = await writer.list_tools()
        if not {"add_memory", "search_memory"}.issubset({t.name for t in tools.tools}):
            raise RuntimeError("Expected upstream MCP tools missing")
        saved = await writer.call_tool("add_memory", {
            "user_message": f"本次跨客户端接力测试的项目代号是 {marker}。项目的固定验收规则：测试通过后仍需人工核对，未确认前不发布。",
            "wait": True,
        })
        if saved.isError or "Stored and extracted" not in text(saved):
            raise RuntimeError("Write did not confirm extraction. Do not repeat the write; inspect Memory Bank.")
        result["written"] = True
        # Keep the writer connection alive so cleanup can target this session later.
        async with connection(settings) as reader:
            deadline = time.monotonic() + timeout
            while True:
                recalled = await reader.call_tool("search_memory", {"query": marker, "top_k": 3})
                if not recalled.isError and marker in text(recalled):
                    result["retrieved"] = True
                    result["matched_memory"] = text(recalled)
                    break
                if time.monotonic() >= deadline:
                    result["note"] = "Index not ready in time. Check Memory Bank; do not duplicate add."
                    break
                await asyncio.sleep(5)
        # Only this newly-created writer's session. Profiles/skills may remain.
        cleanup = await writer.call_tool("forget_session", {})
        result["cleanup_reply"] = text(cleanup)
        result["cleanup_error"] = bool(cleanup.isError)
        result["cleanup_confirmed"] = not cleanup.isError and text(cleanup).startswith("Deleted ")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--allow-write", action="store_true", help="Consent to write a synthetic test and clean its session")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--report", type=Path, help="Optional local report; do not publish private backend data")
    opts = parser.parse_args()
    if not opts.allow_write:
        parser.error("This live test writes one synthetic memory and calls forget_session for its own session. Pass --allow-write.")
    try:
        data = asyncio.run(run(opts.settings, opts.timeout))
    except Exception as exc:
        print(f"Live test stopped ({type(exc).__name__}). A write may have completed; inspect Memory Bank before retrying.", file=sys.stderr)
        raise SystemExit(1) from None
    if opts.report:
        opts.report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in data.items() if k != "matched_memory"}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if data["retrieved"] and data["cleanup_confirmed"] else 1)


if __name__ == "__main__":
    main()
