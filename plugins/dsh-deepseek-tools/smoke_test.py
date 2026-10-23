#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地冒烟测试：不经过 Claude Code，直接以 MCP 客户端调用 server.py。"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = str(Path(__file__).resolve().parent / "server.py")
PYTHON = sys.executable

# 默认用临时文件隔离，避免测试污染真实 HUD 计数。
# SMOKE_REAL=1 时改用真实路径，用于验收“MCP -> 计数文件 -> HUD”全链路。
REAL_RUN = os.environ.get("SMOKE_REAL") == "1"
if REAL_RUN:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from usage_store import usage_path as _usage_path

    USAGE_PATH = str(_usage_path())
else:
    USAGE_DIR = tempfile.mkdtemp(prefix="deepseek-usage-")
    USAGE_PATH = os.path.join(USAGE_DIR, "usage.json")
    os.environ["DEEPSEEK_USAGE_PATH"] = USAGE_PATH


def read_usage() -> dict:
    try:
        with open(USAGE_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {
            "search": {"success": 0},
            "fetch": {"success": 0},
        }


async def main() -> int:
    before = read_usage()
    params = StdioServerParameters(command=PYTHON, args=[SERVER], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("TOOLS:", [(t.name, getattr(t, "title", None)) for t in tools.tools])

            search_result = await session.call_tool(
                "DeepSeek-Search", {"query": "DeepSeek V4 模型 发布", "count": 2}
            )
            print("SEARCH:", search_result.content[0].text[:900])

            # 失败路径：空白 query 在本地校验阶段就返回，不应计数。
            bad_search = await session.call_tool("DeepSeek-Search", {"query": "   "})
            print("BAD_SEARCH:", bad_search.content[0].text[:200])

            fetch_result = await session.call_tool(
                "DeepSeek-Fetch",
                {"url": "https://api-docs.deepseek.com/zh-cn/guides/search/", "max_chars": 400},
            )
            print("FETCH:", fetch_result.content[0].text[:900])

            # 失败路径：非法 URL 在本地校验阶段就返回，不应计数。
            bad_fetch = await session.call_tool("DeepSeek-Fetch", {"url": "not-a-url"})
            print("BAD_FETCH:", bad_fetch.content[0].text[:200])

    usage = read_usage()
    print("USAGE_BEFORE:", json.dumps(before, ensure_ascii=False))
    print("USAGE_AFTER:", json.dumps(usage, ensure_ascii=False))
    assert usage["search"]["success"] - before["search"]["success"] == 1, usage
    assert usage["fetch"]["success"] - before["fetch"]["success"] == 1, usage
    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
