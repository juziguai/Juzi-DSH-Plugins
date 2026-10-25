#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第一轮冒烟测试：直接以 MCP 客户端调用 server.py。

覆盖：
- 工具清单与 schema 可发现
- list_windows 能列出 ChatGPT / WindowsTerminal / 微信
- screenshot 整屏尺寸与 DPI 物理像素一致，缩放元数据与 PNG 实际尺寸一致
- focus_window 能还原最小化的 Notepad++ 并确认前台状态

运行：C:\\Python314\\python.exe smoke_test.py
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
import io
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

SERVER = str(Path(__file__).resolve().parent / "server.py")
PYTHON = sys.executable
EXPECTED_TOOLS = {"list_windows", "focus_window", "screenshot"}


def _image_block(result):
    for item in result.content:
        if getattr(item, "type", "") == "image":
            return item
    return None


async def main() -> int:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)

    params = StdioServerParameters(
        command=PYTHON,
        args=[SERVER],
        env={**os.environ, "JUZI_WIN_DSH_CONFIRM_MODE": "off"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            print("TOOLS:", sorted(names))
            assert names == EXPECTED_TOOLS, names

            result = await session.call_tool("list_windows", {})
            listing = json.loads(result.content[0].text)
            assert listing["ok"], listing
            assert listing["screen"]["width"] == screen_width
            assert listing["screen"]["height"] == screen_height
            print("SCREEN:", listing["screen"], "DPI:", listing["dpi_mode"])
            processes = {item["process"].lower() for item in listing["windows"]}
            for expected in ("chatgpt.exe", "windowsterminal.exe", "weixin.exe"):
                print(f"WINDOW {expected}:", "found" if expected in processes else "MISSING")
            assert "chatgpt.exe" in processes, "未找到 ChatGPT.exe"
            assert "windowsterminal.exe" in processes, "未找到 WindowsTerminal.exe"
            assert "weixin.exe" in processes, "未找到 Weixin.exe"

            result = await session.call_tool("screenshot", {"max_width": 1080})
            meta = json.loads(result.content[0].text)
            image = _image_block(result)
            assert meta["ok"] and image is not None, meta
            assert meta["original_width"] == screen_width, meta
            assert meta["original_height"] == screen_height, meta
            png = Image.open(io.BytesIO(base64.b64decode(image.data)))
            assert png.size == (meta["width"], meta["height"]), (png.size, meta)
            print("SCREENSHOT:", meta["width"], "x", meta["height"], "scale", meta["scale"], "png", png.size)

            notepad = next(
                (item for item in listing["windows"] if item["process"].lower() == "notepad++.exe"),
                None,
            )
            if notepad:
                was_minimized = notepad["minimized"]
                result = await session.call_tool("focus_window", {"hwnd": notepad["hwnd"]})
                focused = json.loads(result.content[0].text)
                assert focused["ok"], focused
                assert focused["window"]["foreground"], focused
                if was_minimized:
                    assert focused["window"]["was_minimized"], focused
                print(
                    "FOCUS:",
                    focused["window"]["title"],
                    "was_minimized=", focused["window"]["was_minimized"],
                    "foreground=", focused["window"]["foreground"],
                )
            else:
                print("FOCUS: Notepad++ 未运行，跳过")

            result = await session.call_tool("focus_window", {})
            invalid = json.loads(result.content[0].text)
            assert invalid["ok"] is False and invalid["error"] == "invalid_args", invalid
            print("INVALID_ARGS: ok")

    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
