#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「电脑控制」MCP stdio 服务。

当前轮次提供只读与窗口定位能力：
- list_windows / focus_window / screenshot

约定：
1. stdout 只走 MCP 协议，日志一律 stderr；操作日志写临时文件，进程退出即删。
2. 进程启动即切 Per-Monitor V2 DPI 感知，所有坐标均为物理像素。
3. 截图返回的 width/height 是缩放后尺寸；屏幕坐标 = origin + 截图坐标 / scale。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

import security
import winapi
from runlog import RunLog

VERSION = "0.1.0"
SERVER_NAME = "win"
CONFIRM_MODE = os.environ.get("JUZI_WIN_DSH_CONFIRM_MODE", "always").strip().lower() or "always"
ALLOWLIST = [
    item.strip().lower()
    for item in os.environ.get("JUZI_WIN_DSH_ALLOWLIST", "").split(";")
    if item.strip()
]

DPI_MODE = winapi.enable_dpi_awareness()
LOG = RunLog()

INSTRUCTIONS = (
    "「电脑控制」面向 Windows 桌面。所有坐标都是物理像素；"
    "screenshot 返回的 width/height 是缩放后的图像尺寸，"
    "scale = width / original_width，屏幕坐标 = origin + 截图坐标 / scale。"
    "带 hwnd 的截图只包含窗口客户区，带 hwnd 的坐标参数相对客户区左上角。"
    "不要操作 UAC、Windows 安全中心或密码管理器窗口；服务端会拒绝。"
)

mcp = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS, log_level="WARNING")


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _error(code: str, message: str, **extra: Any) -> str:
    payload: dict[str, Any] = {"ok": False, "error": code, "message": message}
    payload.update(extra)
    return _dump(payload)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_focus_target(
    hwnd: int | None, process: str | None, title: str | None
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if hwnd is not None:
        info = winapi.window_info(hwnd)
        return info, ([info] if info else [])
    if not process and not title:
        return None, []
    matches = winapi.find_windows(process=process, title=title)
    if not matches:
        return None, []
    matches.sort(key=lambda item: (not item["foreground"], item["minimized"], item["title"]))
    return matches[0], matches[:10]


@mcp.tool(
    name="list_windows",
    title="list_windows",
    description=(
        "列出当前可见的 Windows 顶层窗口：hwnd、进程名、PID、标题、物理像素矩形、"
        "是否最小化、是否前台。可按需包含工具窗口。"
    ),
)
def list_windows(include_tool_windows: bool = False) -> str:
    """列出可见窗口。

    Args:
        include_tool_windows: 是否包含 WS_EX_TOOLWINDOW 窗口（浮动工具条等），默认 False。
    """
    LOG.write("list_windows", "start", {"include_tool_windows": bool(include_tool_windows)})
    try:
        windows = winapi.list_windows(include_tool_windows=bool(include_tool_windows))
    except Exception as exc:  # noqa: BLE001 - 工具边界必须返回结构化错误
        LOG.write("list_windows", "error", error=repr(exc))
        return _error("list_failed", f"枚举窗口失败：{exc}")
    LOG.write("list_windows", "end", outcome=f"{len(windows)} windows")
    return _dump(
        {
            "ok": True,
            "count": len(windows),
            "screen": winapi.screen_metrics(),
            "dpi_mode": DPI_MODE,
            "windows": windows,
        }
    )


@mcp.tool(
    name="focus_window",
    title="focus_window",
    description=(
        "按 hwnd / 进程名 / 标题关键字把窗口切到前台；最小化的窗口先还原。"
        "返回窗口信息与 foreground（是否真正成为前台）。"
    ),
)
def focus_window(
    hwnd: int | None = None,
    process: str | None = None,
    title: str | None = None,
) -> str:
    """切换窗口到前台。

    Args:
        hwnd: 窗口句柄，优先级最高。
        process: 进程名，可带或不带 .exe，例如 notepad++、WindowsTerminal.exe。
        title: 标题关键字，不区分大小写。
    """
    params = {"hwnd": hwnd, "process": process, "title": title}
    LOG.write("focus_window", "start", params)
    if hwnd is None and not process and not title:
        return _error("invalid_args", "hwnd、process、title 至少提供一个。")
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    if process is not None and not isinstance(process, str):
        return _error("invalid_process", "process 必须是字符串。")
    if title is not None and not isinstance(title, str):
        return _error("invalid_title", "title 必须是字符串。")

    target, matches = _resolve_focus_target(hwnd, process, title)
    if target is None:
        LOG.write("focus_window", "error", error="not_found")
        return _error(
            "window_not_found",
            "没有找到匹配的可见窗口。",
            candidates=[{"hwnd": item["hwnd"], "process": item["process"], "title": item["title"]} for item in matches],
        )
    reason = security.forbidden_reason(target)
    if reason:
        LOG.write("focus_window", "blocked", params, target)
        return _error("forbidden_window", reason, window=target)

    try:
        info = winapi.focus_window(target["hwnd"])
    except Exception as exc:  # noqa: BLE001
        LOG.write("focus_window", "error", params, target, error=repr(exc))
        return _error("focus_failed", f"切换窗口失败：{exc}", window=target)

    LOG.write("focus_window", "end", params, info, outcome="foreground" if info["foreground"] else "not_foreground")
    if not info["foreground"]:
        return _dump(
            {
                "ok": False,
                "error": "not_foreground",
                "message": "窗口已尝试还原并置前，但 Windows 未把它设为前台窗口；可重试或手动点击后再操作。",
                "window": info,
            }
        )
    return _dump({"ok": True, "window": info})


@mcp.tool(
    name="screenshot",
    title="screenshot",
    description=(
        "截取整屏（所有显示器）或指定窗口的客户区，返回 PNG 图像与尺寸元数据。"
        "支持 max_width 等比缩放；坐标换算：屏幕坐标 = origin + 截图坐标 / scale。"
    ),
)
def screenshot(hwnd: int | None = None, max_width: int = 1600):
    """截图。

    Args:
        hwnd: 指定窗口句柄时只截客户区；省略则截整个虚拟屏幕。
        max_width: 缩放后的最大宽度，0 表示不缩放；默认 1600，范围 320~4096。
    """
    params = {"hwnd": hwnd, "max_width": max_width}
    LOG.write("screenshot", "start", params)
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return [_error("invalid_hwnd", "hwnd 必须是整数。")]
        hwnd = parsed
    width = _as_int(max_width)
    if width is None:
        return [_error("invalid_max_width", "max_width 必须是整数。")]

    if hwnd is not None:
        info = winapi.window_info(hwnd)
        if info is None:
            return [_error("invalid_hwnd", "窗口句柄无效或窗口已关闭。")]
        reason = security.forbidden_reason(info)
        if reason:
            LOG.write("screenshot", "blocked", params, info)
            return [_error("forbidden_window", reason, window=info)]

    try:
        data, metadata = winapi.capture(max_width=width, hwnd=hwnd)
    except Exception as exc:  # noqa: BLE001
        LOG.write("screenshot", "error", params, error=repr(exc))
        return [_error("screenshot_failed", f"截图失败：{exc}")]

    target = winapi.window_info(hwnd) if hwnd is not None else None
    LOG.write("screenshot", "end", params, target, outcome=f"{metadata['width']}x{metadata['height']}")
    text = _dump(
        {
            "ok": True,
            "message": "图像在下一个 content block；按 metadata 换算坐标。",
            **metadata,
        }
    )
    return [text, Image(data=data, format="png")]


def main() -> int:
    try:
        mcp.run()
    except KeyboardInterrupt:
        return 0
    finally:
        LOG.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
