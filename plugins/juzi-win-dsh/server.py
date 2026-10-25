#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「电脑控制」MCP stdio 服务（纯标准库实现）。

为什么不用 FastMCP：本机实测 `import mcp.server.fastmcp` 冷启动约 3.4 秒，
超过 DSH 的插件启动等待窗口，会被判定为 MCP 启动失败。这里直接实现
MCP 的 initialize / tools/list / tools/call 三个方法，Python 启动只依赖
标准库，MCP 握手在 0.5 秒内完成。

工具：
- list_windows / focus_window / screenshot
- click / scroll / type_text / press_keys
- system

约定：
1. stdout 只走 MCP JSON-RPC（每行一个 JSON），日志一律 stderr。
2. 进程启动即切 Per-Monitor V2 DPI 感知，所有坐标均为物理像素。
3. 截图返回的 width/height 是缩放后尺寸；屏幕坐标 = origin + 截图坐标 / scale。
4. confirm_mode=always/allowlist 时，点击/滚动/输入/按键先返回
   confirmation_required + confirm_token，不执行；模型必须先向用户确认再带 token 重试。
"""

from __future__ import annotations

import base64
import inspect
import json
import os
import sys
import traceback
from typing import Any

import security
import system_control
import winapi
from confirm import ConfirmationGate
from paste_text import paste_text
from runlog import RunLog

VERSION = "1.0.0"
SERVER_NAME = "win"
CONFIRM_MODE = os.environ.get("JUZI_WIN_DSH_CONFIRM_MODE", "always").strip().lower() or "always"
ALLOWLIST = [
    item.strip().lower()
    for item in os.environ.get("JUZI_WIN_DSH_ALLOWLIST", "").split(";")
    if item.strip()
]

DPI_MODE = winapi.enable_dpi_awareness()
LOG = RunLog()
GATE = ConfirmationGate(CONFIRM_MODE, ALLOWLIST)

INSTRUCTIONS = (
    "「电脑控制」面向 Windows 桌面。所有坐标都是物理像素；"
    "screenshot 返回的 width/height 是缩放后的图像尺寸，"
    "scale = width / original_width，屏幕坐标 = origin + 截图坐标 / scale。"
    "带 hwnd 的截图只包含窗口客户区（Chrome/Electron 窗口自动回退为屏幕客户区截图）；"
    "带 hwnd 的坐标参数相对客户区左上角。"
    "confirm_mode=always 时，click/scroll/type_text/press_keys 第一次调用只返回 "
    "confirmation_required，必须先在 dsh 里向用户确认，再带 confirm_token 重试；"
    "没有 token 绝不会执行。不要操作 UAC、Windows 安全中心或密码管理器窗口。"
)


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


def _gate(
    action: str,
    params: dict[str, Any],
    target: dict[str, Any] | None,
    confirm_token: str | None,
) -> str | None:
    """需要确认时返回 confirmation 响应；返回 None 表示可以执行。"""
    reason = security.forbidden_reason(target)
    if reason:
        return _error("forbidden_window", reason, window=target)
    if not GATE.needs_confirmation(target):
        return None

    preview = dict(params)
    if isinstance(preview.get("text"), str) and len(preview["text"]) > 200:
        preview["text"] = preview["text"][:200] + "…"
    if not isinstance(confirm_token, str) or not confirm_token.strip():
        info = GATE.issue(action, params, target)
        return _dump(
            {
                "ok": False,
                "error": "confirmation_required",
                "message": (
                    "该操作尚未执行。请先在 dsh 里向用户说明 action、目标和参数并取得确认；"
                    "用户确认后，用同一个 confirm_token 重新调用。"
                ),
                "action": action,
                "target": target,
                "params": preview,
                **info,
            }
        )
    ok, why = GATE.verify(action, params, target, confirm_token.strip())
    if not ok:
        info = GATE.issue(action, params, target)
        return _dump(
            {
                "ok": False,
                "error": "invalid_confirm_token",
                "message": why,
                "action": action,
                "target": target,
                "params": preview,
                **info,
            }
        )
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


# ---------------------------------------------------------------- 工具实现

def list_windows(include_tool_windows: bool = False) -> str:
    LOG.write("list_windows", "start", {"include_tool_windows": bool(include_tool_windows)})
    try:
        windows = winapi.list_windows(include_tool_windows=bool(include_tool_windows))
    except Exception as exc:  # noqa: BLE001
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


def focus_window(
    hwnd: int | None = None,
    process: str | None = None,
    title: str | None = None,
) -> str:
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
            candidates=[
                {"hwnd": item["hwnd"], "process": item["process"], "title": item["title"]}
                for item in matches
            ],
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

    LOG.write(
        "focus_window", "end", params, info,
        outcome="foreground" if info["foreground"] else "not_foreground",
    )
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


def screenshot(hwnd: int | None = None, max_width: int = 1600) -> list[dict[str, Any]]:
    params = {"hwnd": hwnd, "max_width": max_width}
    LOG.write("screenshot", "start", params)
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return [{"type": "text", "text": _error("invalid_hwnd", "hwnd 必须是整数。")}]
        hwnd = parsed
    width = _as_int(max_width)
    if width is None:
        return [{"type": "text", "text": _error("invalid_max_width", "max_width 必须是整数。")}]

    if hwnd is not None:
        info = winapi.window_info(hwnd)
        if info is None:
            return [{"type": "text", "text": _error("invalid_hwnd", "窗口句柄无效或窗口已关闭。")}]
        reason = security.forbidden_reason(info)
        if reason:
            LOG.write("screenshot", "blocked", params, info)
            return [{"type": "text", "text": _error("forbidden_window", reason, window=info)}]

    try:
        data, metadata = winapi.capture(max_width=width, hwnd=hwnd)
    except Exception as exc:  # noqa: BLE001
        LOG.write("screenshot", "error", params, error=repr(exc))
        return [{"type": "text", "text": _error("screenshot_failed", f"截图失败：{exc}")}]

    target = winapi.window_info(hwnd) if hwnd is not None else None
    LOG.write(
        "screenshot", "end", params, target,
        outcome=f"{metadata['width']}x{metadata['height']}",
    )
    text = _dump(
        {
            "ok": True,
            "message": "图像在下一个 content block；按 metadata 换算坐标。",
            **metadata,
        }
    )
    return [
        {"type": "text", "text": text},
        {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": "image/png"},
    ]


def click(
    x: int,
    y: int,
    button: str = "left",
    double: bool = False,
    hwnd: int | None = None,
    confirm_token: str | None = None,
) -> str:
    params = {"x": x, "y": y, "button": button, "double": bool(double), "hwnd": hwnd}
    LOG.write("click", "start", params)
    x_value, y_value = _as_int(x), _as_int(y)
    if x_value is None or y_value is None:
        return _error("invalid_args", "x、y 必须是整数物理像素。")
    if button not in ("left", "right"):
        return _error("invalid_button", "button 必须是 left 或 right。")
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    try:
        screen_x, screen_y = winapi.resolve_click_point(x_value, y_value, hwnd)
    except ValueError as exc:
        return _error("invalid_coordinates", str(exc))
    target = winapi.window_info(hwnd) if hwnd is not None else winapi.window_at_point(screen_x, screen_y)
    blocked = _gate("click", params, target, confirm_token)
    if blocked:
        LOG.write("click", "pending_confirmation", params, target)
        return blocked
    try:
        result = winapi.click(x_value, y_value, button=button, double=bool(double), hwnd=hwnd)
    except Exception as exc:  # noqa: BLE001
        LOG.write("click", "error", params, target, error=repr(exc))
        return _error("click_failed", f"点击失败：{exc}")
    LOG.write("click", "end", params, result.get("target"), outcome=f"{result['x']},{result['y']}")
    return _dump({"ok": True, **result})


def scroll(
    clicks: int = 3,
    x: int | None = None,
    y: int | None = None,
    confirm_token: str | None = None,
) -> str:
    params = {"clicks": clicks, "x": x, "y": y}
    LOG.write("scroll", "start", params)
    clicks_value = _as_int(clicks)
    if clicks_value is None or clicks_value == 0 or abs(clicks_value) > 20:
        return _error("invalid_clicks", "clicks 必须是 -20~20 之间的非零整数。")
    if (x is None) != (y is None):
        return _error("invalid_coordinates", "x 和 y 必须同时提供或同时省略。")
    x_value = y_value = None
    if x is not None:
        x_value, y_value = _as_int(x), _as_int(y)
        if x_value is None or y_value is None:
            return _error("invalid_coordinates", "x、y 必须是整数物理像素。")
        try:
            winapi.resolve_click_point(x_value, y_value)
        except ValueError as exc:
            return _error("invalid_coordinates", str(exc))
        target = winapi.window_at_point(x_value, y_value)
    else:
        cursor = winapi.current_cursor()
        target = winapi.window_at_point(cursor["x"], cursor["y"])
    blocked = _gate("scroll", params, target, confirm_token)
    if blocked:
        LOG.write("scroll", "pending_confirmation", params, target)
        return blocked
    try:
        result = winapi.scroll(clicks_value, x_value, y_value)
    except Exception as exc:  # noqa: BLE001
        LOG.write("scroll", "error", params, target, error=repr(exc))
        return _error("scroll_failed", f"滚动失败：{exc}")
    LOG.write("scroll", "end", params, result.get("target"), outcome=str(result["delta"]))
    return _dump({"ok": True, **result})


def type_text(
    text: str,
    method: str = "paste",
    confirm_token: str | None = None,
) -> str:
    if not isinstance(text, str) or text == "":
        return _error("invalid_text", "text 必须是非空字符串。")
    if len(text) > 100000:
        return _error("invalid_text", "text 不能超过 100000 个字符。")
    if method not in ("paste", "unicode"):
        return _error("invalid_method", "method 必须是 paste 或 unicode。")
    params = {"text": text, "method": method}
    LOG.write("type_text", "start", {"text": text[:2000], "chars": len(text), "method": method})
    target = winapi.foreground_info()
    if target is None:
        return _error("no_foreground", "当前没有前台窗口，无法输入。")
    blocked = _gate("type_text", params, target, confirm_token)
    if blocked:
        LOG.write("type_text", "pending_confirmation", {"chars": len(text)}, target)
        return blocked
    try:
        if method == "unicode":
            result = winapi.type_text(text)
            payload = {"ok": True, **result, "method": "unicode", "clipboard_restored": None, "target": target}
        else:
            pasted = paste_text(text)
            payload = {
                "ok": True,
                "characters": len(text),
                "method": "paste",
                "clipboard_restored": bool(pasted.get("restored")),
                "target": target,
            }
    except Exception as exc:  # noqa: BLE001
        LOG.write("type_text", "error", {"chars": len(text), "method": method}, target, error=repr(exc))
        return _error("type_text_failed", f"输入失败：{exc}")
    LOG.write(
        "type_text", "end", {"chars": len(text), "method": method}, target,
        outcome=f"{payload['characters']} chars",
    )
    return _dump(payload)


def press_keys(keys: str, confirm_token: str | None = None) -> str:
    if not isinstance(keys, str) or not keys.strip():
        return _error("invalid_keys", "keys 必须是非空字符串。")
    params = {"keys": keys.strip()}
    LOG.write("press_keys", "start", params)
    target = winapi.foreground_info()
    if target is None:
        return _error("no_foreground", "当前没有前台窗口，无法按键。")
    blocked = _gate("press_keys", params, target, confirm_token)
    if blocked:
        LOG.write("press_keys", "pending_confirmation", params, target)
        return blocked
    try:
        result = winapi.press_keys(keys)
    except Exception as exc:  # noqa: BLE001
        LOG.write("press_keys", "error", params, target, error=repr(exc))
        return _error("press_keys_failed", f"按键失败：{exc}")
    LOG.write("press_keys", "end", params, target, outcome=result["keys"])
    return _dump({"ok": True, **result, "target": target})


def system(
    brightness: int | None = None,
    volume: int | None = None,
    mute: bool | None = None,
    lock: bool = False,
) -> str:
    request: dict[str, Any] = {}
    if brightness is not None:
        value = _as_int(brightness)
        if value is None or not 0 <= value <= 100:
            return _error("invalid_brightness", "brightness 必须是 0~100 的整数。")
        request["brightness"] = value
    if volume is not None:
        value = _as_int(volume)
        if value is None or not 0 <= value <= 100:
            return _error("invalid_volume", "volume 必须是 0~100 的整数。")
        request["volume"] = value
    if mute is not None:
        if not isinstance(mute, bool):
            return _error("invalid_mute", "mute 必须是布尔值。")
        request["mute"] = mute
    if lock:
        request["lock"] = True

    LOG.write("system", "start", request)
    try:
        result = system_control.apply_system(request)
    except Exception as exc:  # noqa: BLE001
        LOG.write("system", "error", request, error=repr(exc))
        return _error("system_failed", f"系统控制失败：{exc}")
    if not result.get("ok"):
        LOG.write("system", "error", request, error=str(result.get("errors")))
        return _error("system_failed", "系统控制未完全成功。", details=result)
    LOG.write("system", "end", request, outcome=json.dumps(result, ensure_ascii=False))
    return _dump({"ok": True, **result})


# ---------------------------------------------------------------- MCP 协议

_WINDOW_SCHEMA = {
    "type": "object",
    "properties": {
        "include_tool_windows": {"type": "boolean", "default": False, "description": "是否包含工具窗口（浮动工具条等）。"},
    },
}
_FOCUS_SCHEMA = {
    "type": "object",
    "properties": {
        "hwnd": {"type": ["integer", "null"], "default": None, "description": "窗口句柄，优先级最高。"},
        "process": {"type": ["string", "null"], "default": None, "description": "进程名，可带或不带 .exe。"},
        "title": {"type": ["string", "null"], "default": None, "description": "标题关键字，不区分大小写。"},
    },
}
_SCREENSHOT_SCHEMA = {
    "type": "object",
    "properties": {
        "hwnd": {"type": ["integer", "null"], "default": None, "description": "窗口句柄；省略则截整屏。"},
        "max_width": {"type": "integer", "default": 1600, "minimum": 0, "maximum": 4096, "description": "缩放后最大宽度，0 表示不缩放。"},
    },
}
_CLICK_SCHEMA = {
    "type": "object",
    "properties": {
        "x": {"type": "integer", "description": "物理像素 X；有 hwnd 时为客户区相对 X。"},
        "y": {"type": "integer", "description": "物理像素 Y；有 hwnd 时为客户区相对 Y。"},
        "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
        "double": {"type": "boolean", "default": False},
        "hwnd": {"type": ["integer", "null"], "default": None},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["x", "y"],
}
_SCROLL_SCHEMA = {
    "type": "object",
    "properties": {
        "clicks": {"type": "integer", "default": 3, "minimum": -20, "maximum": 20, "description": "正数向上、负数向下。"},
        "x": {"type": ["integer", "null"], "default": None},
        "y": {"type": ["integer", "null"], "default": None},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
}
_TYPE_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "要输入的文本，支持中文、换行与制表符。"},
        "method": {"type": "string", "enum": ["paste", "unicode"], "default": "paste", "description": "paste 使用剪贴板并恢复；unicode 使用 SendInput。"},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["text"],
}
_KEYS_SCHEMA = {
    "type": "object",
    "properties": {
        "keys": {"type": "string", "description": "组合键，例如 ctrl+a、ctrl+c、alt+tab、win+d、f5。"},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["keys"],
}
_SYSTEM_SCHEMA = {
    "type": "object",
    "properties": {
        "brightness": {"type": ["integer", "null"], "default": None, "minimum": 0, "maximum": 100},
        "volume": {"type": ["integer", "null"], "default": None, "minimum": 0, "maximum": 100},
        "mute": {"type": ["boolean", "null"], "default": None},
        "lock": {"type": "boolean", "default": False},
    },
}

TOOLS = [
    {
        "name": "list_windows",
        "description": "列出当前可见的 Windows 顶层窗口：hwnd、进程名、PID、标题、物理像素矩形、是否最小化、是否前台。",
        "inputSchema": _WINDOW_SCHEMA,
    },
    {
        "name": "focus_window",
        "description": "按 hwnd / 进程名 / 标题关键字把窗口切到前台；最小化的窗口先还原。返回 foreground 表示是否真正成为前台。",
        "inputSchema": _FOCUS_SCHEMA,
    },
    {
        "name": "screenshot",
        "description": "截取整屏（所有显示器）或指定窗口的客户区，返回 PNG 图像与尺寸元数据。坐标换算：屏幕坐标 = origin + 截图坐标 / scale。",
        "inputSchema": _SCREENSHOT_SCHEMA,
    },
    {
        "name": "click",
        "description": "在物理像素坐标点击鼠标。button=left/right，double=true 为双击；提供 hwnd 时 x/y 相对客户区左上角。confirm_mode 需要确认时第一次只返回 confirmation_required。",
        "inputSchema": _CLICK_SCHEMA,
    },
    {
        "name": "scroll",
        "description": "在指定物理像素坐标滚动鼠标滚轮；clicks 正数向上、负数向下。省略 x/y 时在当前位置滚动。confirm_mode 需要确认时第一次只返回 confirmation_required。",
        "inputSchema": _SCROLL_SCHEMA,
    },
    {
        "name": "type_text",
        "description": "向当前前台窗口输入任意文本（含中文、换行、制表符）。默认剪贴板粘贴并恢复原剪贴板；method=unicode 时不占用剪贴板。confirm_mode 需要确认时第一次只返回 confirmation_required。",
        "inputSchema": _TYPE_SCHEMA,
    },
    {
        "name": "press_keys",
        "description": "向当前前台窗口发送按键或组合键，如 enter、ctrl+v、alt+tab、win+d。confirm_mode 需要确认时第一次只返回 confirmation_required。",
        "inputSchema": _KEYS_SCHEMA,
    },
    {
        "name": "system",
        "description": "系统控制：亮度 0~100（WMI，读回确认）、音量 0~100、静音、锁屏。不传参数时只读取当前状态。",
        "inputSchema": _SYSTEM_SCHEMA,
    },
]

TOOL_FUNCTIONS = {
    "list_windows": list_windows,
    "focus_window": focus_window,
    "screenshot": screenshot,
    "click": click,
    "scroll": scroll,
    "type_text": type_text,
    "press_keys": press_keys,
    "system": system,
}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {
            "content": [{"type": "text", "text": f'未知工具：{name}'}],
            "isError": True,
        }
    allowed = {parameter.name for parameter in inspect.signature(function).parameters.values()}
    kwargs = {key: value for key, value in arguments.items() if key in allowed}
    try:
        result = function(**kwargs)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        result = _error("tool_exception", f"{name} 执行异常：{exc}")
    if isinstance(result, list):
        content = result
    else:
        content = [{"type": "text", "text": str(result)}]
    return {"content": content, "isError": False}


def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        requested = message.get("params", {}).get("protocolVersion")
        protocol = requested if isinstance(requested, str) and requested else "2024-11-05"
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": protocol,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": VERSION},
                "instructions": INSTRUCTIONS,
            },
        }
    if method == "notifications/initialized" or (isinstance(method, str) and method.startswith("notifications/")):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": "tools/call 需要 name 和 arguments 对象。"},
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": _call_tool(name, arguments)}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if request_id is None:
        return None
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"不支持的方法：{method}"},
    }


def serve() -> int:
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"[juzi-win-dsh] 无效 JSON：{exc}", file=sys.stderr)
            continue
        if not isinstance(message, dict):
            continue
        try:
            response = _handle(message)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            if message.get("id") is not None:
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32603, "message": f"内部错误：{exc}"},
                }
            else:
                response = None
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


def main() -> int:
    try:
        return serve()
    except KeyboardInterrupt:
        return 0
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        return 1
    finally:
        LOG.close()


if __name__ == "__main__":
    sys.exit(main())
