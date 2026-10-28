#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真机冒烟测试：以 MCP 客户端调用 server.py。

安全边界：
- 只做只读/窗口焦点/截图/系统状态读取；不点击、不输入、不按键、不写剪贴板、不改音量亮度。
- 不触碰 Notepad++ 任何已有文档；只截图和置前，最小化后还原。
- 临时文件使用 .tmp-* 前缀并在测试后删除。

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import launcher  # noqa: E402
import ocr  # noqa: E402
import security  # noqa: E402
from confirm import ConfirmationGate  # noqa: E402

SERVER = str(Path(__file__).resolve().parent / "server.py")
PYTHON = sys.executable
EXPECTED_TOOLS = {
    "list_windows", "focus_window", "screenshot",
    "click", "scroll", "type_text", "press_keys", "system",
    "manage_window", "hover", "drag", "wait", "clipboard", "launch_app", "find_text",
    "get_focused_text", "input_batch",
}


def _image_block(result):
    for item in result.content:
        if getattr(item, "type", "") == "image":
            return item
    return None


def _unit_checks() -> None:
    gate = ConfirmationGate("always", [])
    target = {"hwnd": 1, "process": "notepad++.exe", "title": "新文件 - Notepad++"}
    assert gate.needs_confirmation(target)
    issued = gate.issue("click", {"x": 10, "y": 20}, target)
    ok, reason = gate.verify("click", {"x": 10, "y": 20}, target, issued["confirm_token"])
    assert ok, reason
    ok, _ = gate.verify("click", {"x": 10, "y": 20}, target, issued["confirm_token"])
    assert not ok, "确认令牌必须一次性"

    close_params = {"action": "close", "hwnd": 1, "process": None, "title": None}
    close_token = gate.issue("manage_window.close", close_params, target)
    ok, _ = gate.verify(
        "manage_window.close", {**close_params, "action": "tile"}, target,
        close_token["confirm_token"],
    )
    assert not ok, "令牌必须绑定 action/参数"
    ok, _ = gate.verify("manage_window.close", close_params, target, close_token["confirm_token"])
    assert ok, "完整参数重试应通过"

    bypass = ConfirmationGate("allowlist", ["notepad++.exe"])
    assert not bypass.needs_confirmation(target)
    assert security.forbidden_reason({"process": "consent.exe", "title": "x"})
    assert security.forbidden_reason({"process": "chrome.exe", "title": "1Password - 登录"})
    assert not security.forbidden_reason({"process": "notepad++.exe", "title": "*新文件 - Notepad++"})

    try:
        launcher._validate_path("notepad.exe")
        raise AssertionError("相对路径必须被拒绝")
    except ValueError:
        pass
    try:
        launcher._validate_path(r"C:\Windows\System32\cmd.exe")
        raise AssertionError("cmd.exe 必须被拒绝")
    except PermissionError:
        pass

    # 同一视觉行被 Windows OCR 拆成多个 OcrLine 时的拼接匹配。
    lines = [
        {"text": "验 收 找 字", "words": [
            {"text": "验", "x": 0, "y": 0, "w": 20, "h": 20},
            {"text": "收", "x": 22, "y": 0, "w": 20, "h": 20},
            {"text": "找", "x": 44, "y": 0, "w": 20, "h": 20},
            {"text": "字", "x": 66, "y": 0, "w": 20, "h": 20},
        ]},
        {"text": "ABC", "words": [{"text": "ABC", "x": 100, "y": 2, "w": 40, "h": 16}]},
    ]
    hits = ocr.find_matches(lines, "验收找字 ABC", "contains", 5)
    assert len(hits) == 1, hits
    assert hits[0]["cx"] == 70, hits
    print("UNIT: confirm token / allowlist / forbidden list / launcher / OCR row-merge OK")


async def main() -> int:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)
    _unit_checks()

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
            assert names == EXPECTED_TOOLS, {
                "missing": sorted(EXPECTED_TOOLS - names),
                "unexpected": sorted(names - EXPECTED_TOOLS),
            }

            result = await session.call_tool("list_windows", {})
            listing = json.loads(result.content[0].text)
            assert listing["ok"], listing
            assert listing["screen"]["width"] == screen_width
            assert listing["screen"]["height"] == screen_height
            print("SCREEN:", listing["screen"], "DPI:", listing["dpi_mode"])
            processes = {item["process"].lower() for item in listing["windows"]}
            for expected in ("chatgpt.exe", "windowsterminal.exe", "weixin.exe"):
                print(f"WINDOW {expected}:", "found" if expected in processes else "MISSING")
            assert listing["count"] > 0

            result = await session.call_tool("manage_window", {"action": "get_work_area"})
            work = json.loads(result.content[0].text)
            assert work["ok"] and work["monitors"], work
            assert work["monitors"][0]["work_area"]["height"] < work["monitors"][0]["monitor"]["height"]
            print("WORK_AREA:", work["monitors"][0]["work_area"], "primary:", work["primary_index"])

            result = await session.call_tool("screenshot", {"max_width": 1080})
            meta = json.loads(result.content[0].text)
            image = _image_block(result)
            assert meta["ok"] and image is not None, meta
            assert meta["original_width"] == screen_width, meta
            assert meta["original_height"] == screen_height, meta
            png = Image.open(io.BytesIO(base64.b64decode(image.data)))
            assert png.size == (meta["width"], meta["height"]), (png.size, meta)
            print("SCREENSHOT:", meta["width"], "x", meta["height"], "scale", meta["scale"], "png", png.size)

            result = await session.call_tool("clipboard", {"action": "get"})
            clip = json.loads(result.content[0].text)
            assert clip["ok"] and "empty" in clip, clip
            print("CLIPBOARD_READ:", "empty" if clip["empty"] else f"{clip['length']} chars", "truncated=", clip["truncated"])

            result = await session.call_tool("wait", {
                "condition": "timeout", "timeout_ms": 250, "poll_ms": 100,
            })
            waited = json.loads(result.content[0].text)
            assert waited["ok"] and not waited["timed_out"] and waited["elapsed_ms"] >= 200, waited
            print("WAIT_TIMEOUT:", waited["elapsed_ms"], "ms")

            result = await session.call_tool("find_text", {
                "text": "Notepad++",
                "region": {"x": 0, "y": 0, "width": 600, "height": 240},
                "max_results": 1,
            })
            found = json.loads(result.content[0].text)
            if found.get("ok"):
                print("FIND_TEXT: engine", found.get("engine"), "hits", found.get("count"))
            else:
                assert found.get("error") == "ocr_unavailable", found
                print("FIND_TEXT: OCR 引擎不可用，跳过（已返回 ocr_unavailable）")

            notepad = next(
                (item for item in listing["windows"] if item["process"].lower() == "notepad++.exe"),
                None,
            )
            if notepad:
                was_minimized = notepad["minimized"]
                result = await session.call_tool("focus_window", {"process": "notepad++"})
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

                result = await session.call_tool(
                    "screenshot", {"hwnd": focused["window"]["hwnd"], "max_width": 800}
                )
                window_meta = json.loads(result.content[0].text)
                window_image = _image_block(result)
                assert window_meta["ok"] and window_image is not None, window_meta
                assert window_meta["mode"] == "window" and window_meta["hwnd"] == focused["window"]["hwnd"]
                window_png = Image.open(io.BytesIO(base64.b64decode(window_image.data)))
                assert window_png.size == (window_meta["width"], window_meta["height"])
                print(
                    "WINDOW_SCREENSHOT:",
                    window_meta["width"], "x", window_meta["height"],
                    "origin", window_meta["origin"],
                )
            else:
                print("FOCUS: Notepad++ 未运行，跳过")

            result = await session.call_tool("system", {})
            status = json.loads(result.content[0].text)
            assert status["ok"], status
            assert isinstance(status["brightness"], int)
            assert isinstance(status["volume"], int)
            assert isinstance(status["mute"], bool)
            print("SYSTEM_READ:", status)

            result = await session.call_tool("focus_window", {})
            invalid = json.loads(result.content[0].text)
            assert invalid["ok"] is False and invalid["error"] == "invalid_args", invalid
            print("INVALID_ARGS: ok")

            result = await session.call_tool("manage_window", {"action": "get_work_area", "bogus": 1})
            invalid = json.loads(result.content[0].text)
            assert invalid["ok"] is False and invalid["error"] == "invalid_arguments", invalid
            print("MANAGE_INVALID_ARGS: ok")

    print("SMOKE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
