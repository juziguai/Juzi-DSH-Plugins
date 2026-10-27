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
import time
import traceback
from io import BytesIO
from typing import Any

import clipboard_win
import launcher
import ocr
import schema_validate
import security
import system_control
import winapi
from confirm import ConfirmationGate
from paste_text import paste_text
from runlog import RunLog

VERSION = "1.1.0"
SERVER_NAME = "win"
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
MAX_FRAME_BYTES = 1024 * 1024
MAX_JSON_INT_DIGITS = 1000
MAX_JSON_DEPTH = 200
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
    "confirm_mode=always 时，所有写操作第一次调用只返回 confirmation_required + confirm_token，"
    "必须先在 dsh 里向用户说明 action、目标和参数并取得确认，再带 confirm_token 重试；"
    "没有 token 绝不会执行。该 token 是模型侧两阶段协议，服务端无法证明 token 由人工批准，"
    "宿主原生审批/权限预设仍是外层控制。"
    "system 无参数只读免确认；包含 brightness/volume/mute/lock 的写请求同样走确认门。"
    "find_text 返回的 cx/cy 是屏幕物理像素，可直接传给 click；OCR 只读、仍走 click 的确认门。"
    "不要操作 UAC、Windows 安全中心或密码管理器窗口。"
)


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _error(code: str, message: str, status: str | None = None, **extra: Any) -> str:
    payload: dict[str, Any] = {"ok": False, "error": code, "error_code": code, "message": message}
    if status:
        payload["status"] = status
    payload.update(extra)
    return _dump(payload)


def _as_int(value: Any) -> int | None:
    """严格整数：拒绝 bool、float、字符串；MCP 入口另有 JSON Schema 校验。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


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
                "error_code": "confirmation_required",
                "status": "confirmation_required",
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
                "error_code": "invalid_confirm_token",
                "status": "confirmation_invalid",
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
                "error_code": "not_foreground",
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
            capture_rect = winapi.client_metrics(hwnd)
        except Exception as exc:  # noqa: BLE001
            return [{"type": "text", "text": _error("screenshot_failed", f"读取客户区失败：{exc}")}]
    else:
        capture_rect = winapi.screen_metrics()
        capture_rect = {
            "x": capture_rect["x"], "y": capture_rect["y"],
            "width": capture_rect["width"], "height": capture_rect["height"],
        }

    forbidden_hits = security.forbidden_windows(capture_rect)
    if forbidden_hits:
        LOG.write("screenshot", "blocked", params, None)
        return [
            {
                "type": "text",
                "text": _error(
                    "forbidden_window",
                    "截图区域与受保护窗口相交，已拒绝；请先关闭或移动受保护窗口。",
                    windows=forbidden_hits,
                ),
            }
        ]

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
        target = winapi.window_at_point(screen_x, screen_y)
    except ValueError as exc:
        return _error("invalid_coordinates", str(exc))
    if hwnd is not None and (target is None or int(target["hwnd"]) != int(hwnd)):
        LOG.write("click", "blocked", params, target, outcome="target_mismatch")
        return _error(
            "target_mismatch",
            "请求的 hwnd 与屏幕落点实际顶层窗口不一致；hwnd 不能替代真实命中对象，已拒绝。",
            requested_hwnd=hwnd,
            actual_window=target,
        )
    blocked = _gate("click", params, target, confirm_token)
    if blocked:
        LOG.write("click", "pending_confirmation", params, target)
        return blocked
    try:
        result = winapi.click(
            x_value, y_value, button=button, double=bool(double), hwnd=hwnd,
            expected_hwnd=None if target is None else int(target["hwnd"]),
        )
    except ValueError as exc:
        LOG.write("click", "blocked", params, target, outcome="target_changed")
        return _error("target_changed", str(exc), window=target)
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
        result = winapi.scroll(
            clicks_value, x_value, y_value,
            expected_hwnd=None if target is None else int(target["hwnd"]),
        )
    except ValueError as exc:
        LOG.write("scroll", "blocked", params, target, outcome="target_changed")
        return _error("target_changed", str(exc), window=target)
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
        current = winapi.foreground_info()
        if current is None or int(current["hwnd"]) != int(target["hwnd"]):
            return _error(
                "target_changed",
                "派发前前台窗口已变化，已中止输入；请重新确认目标窗口。",
                expected=target,
                actual=current,
            )
        if method == "unicode":
            result = winapi.type_text(text, expected_hwnd=int(target["hwnd"]))
            payload = {"ok": True, **result, "method": "unicode", "clipboard_restored": None, "target": target}
        else:
            pasted = paste_text(text, expected_hwnd=int(target["hwnd"]))
            if not pasted.get("paste_ok"):
                return _error(
                    "target_changed" if pasted.get("target_changed") else ("clipboard_backup_failed" if pasted.get("backup_status") == "failed" else "type_text_failed"),
                    "粘贴未执行或未成功；详见 details。",
                    details=pasted,
                    target=target,
                )
            payload = {
                "ok": True,
                "characters": len(text),
                "method": "paste",
                "paste_ok": bool(pasted.get("paste_ok")),
                "clipboard_restored": bool(pasted.get("restore_ok")),
                "clipboard_restore_conflict": bool(pasted.get("restore_conflict")),
                "clipboard_backup_status": pasted.get("backup_status"),
                "target": target,
            }
    except ValueError as exc:
        LOG.write("type_text", "blocked", {"chars": len(text), "method": method}, target, outcome="target_changed")
        return _error("target_changed", str(exc), window=target)
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
        current = winapi.foreground_info()
        if current is None or int(current["hwnd"]) != int(target["hwnd"]):
            return _error(
                "target_changed",
                "派发前前台窗口已变化，已中止按键。",
                expected=target,
                actual=current,
            )
        result = winapi.press_keys(keys, expected_hwnd=int(target["hwnd"]))
    except ValueError as exc:
        LOG.write("press_keys", "blocked", params, target, outcome="target_changed")
        return _error("target_changed", str(exc), window=target)
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
    confirm_token: str | None = None,
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
    if request:
        blocked = _gate("system", request, None, confirm_token)
        if blocked:
            LOG.write("system", "pending_confirmation", request)
            return blocked
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


# ---------------------------------------------------------------- 1.1.0 新工具

_MANAGE_ACTIONS = {
    "move", "resize", "set_bounds", "minimize", "maximize",
    "restore", "close", "tile", "get_work_area",
}
_TILE_PRESETS = {
    "left_half", "right_half", "top_left", "top_right",
    "bottom_left", "bottom_right", "maximize",
}


def _normal_window_rect(hwnd: int) -> dict[str, int]:
    """move/resize 前先还原最大化/最小化，取正常状态下的可见矩形。"""
    info = winapi.window_info(hwnd)
    if info is None:
        raise ValueError("窗口句柄无效或窗口已关闭。")
    if winapi.window_state(hwnd) != "normal":
        winapi.set_window_state(hwnd, "restore")
        info = winapi.window_info(hwnd)
        if info is None:
            raise ValueError("窗口在还原后已关闭。")
    return info["rect"]


def manage_window(
    action: str,
    hwnd: int | None = None,
    process: str | None = None,
    title: str | None = None,
    x: int | None = None,
    y: int | None = None,
    width: int | None = None,
    height: int | None = None,
    tile: str | None = None,
    monitor: int = 0,
    confirm_token: str | None = None,
) -> str:
    if not isinstance(action, str) or action.strip().lower() not in _MANAGE_ACTIONS:
        return _error("invalid_action", f"action 必须是：{', '.join(sorted(_MANAGE_ACTIONS))}。")
    action = action.strip().lower()
    params = {
        "action": action, "hwnd": hwnd, "process": process, "title": title,
        "x": x, "y": y, "width": width, "height": height,
        "tile": tile, "monitor": monitor,
    }
    LOG.write("manage_window", "start", params)

    if action == "get_work_area":
        try:
            rows = winapi.monitors()
        except Exception as exc:  # noqa: BLE001
            return _error("work_area_failed", f"枚举显示器失败：{exc}")
        primary = next((row["index"] for row in rows if row["primary"]), None)
        return _dump(
            {
                "ok": True,
                "count": len(rows),
                "primary_index": primary,
                "monitors": rows,
                "screen": winapi.screen_metrics(),
            }
        )

    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    if process is not None and not isinstance(process, str):
        return _error("invalid_process", "process 必须是字符串。")
    if title is not None and not isinstance(title, str):
        return _error("invalid_title", "title 必须是字符串。")
    if hwnd is None and not process and not title:
        return _error("invalid_args", "hwnd、process、title 至少提供一个。")

    target, matches = _resolve_focus_target(hwnd, process, title)
    if target is None:
        LOG.write("manage_window", "error", params, error="not_found")
        return _error(
            "window_not_found",
            "没有找到匹配的可见窗口。",
            candidates=[
                {"hwnd": item["hwnd"], "process": item["process"], "title": item["title"]}
                for item in matches
            ],
        )

    # 先校验 action 专属参数，避免参数不全时反而发出确认令牌。
    prepared: dict[str, Any] = {}
    if action == "move":
        x_value, y_value = _as_int(x), _as_int(y)
        if x_value is None or y_value is None:
            return _error("invalid_args", "move 需要整数 x 和 y。")
        prepared = {"x": x_value, "y": y_value}
    elif action == "resize":
        width_value, height_value = _as_int(width), _as_int(height)
        if width_value is None or height_value is None or width_value <= 0 or height_value <= 0:
            return _error("invalid_args", "resize 需要正整数 width 和 height。")
        prepared = {"width": width_value, "height": height_value}
    elif action == "set_bounds":
        values = [_as_int(x), _as_int(y), _as_int(width), _as_int(height)]
        if any(value is None for value in values):
            return _error("invalid_args", "set_bounds 需要整数 x、y、width、height。")
        if values[2] <= 0 or values[3] <= 0:
            return _error("invalid_args", "width、height 必须是正整数。")
        prepared = {"x": values[0], "y": values[1], "width": values[2], "height": values[3]}
    elif action == "tile":
        if not isinstance(tile, str) or tile.strip().lower() not in _TILE_PRESETS:
            return _error("invalid_args", f"tile 必须是：{', '.join(sorted(_TILE_PRESETS))}。")
        monitor_value = _as_int(monitor)
        if monitor_value is None or monitor_value < 0:
            return _error("invalid_args", "monitor 必须是 >=0 的整数。")
        prepared = {"tile": tile.strip().lower(), "monitor": monitor_value}

    blocked = _gate(f"manage_window.{action}", params, target, confirm_token)
    if blocked:
        LOG.write("manage_window", "pending_confirmation", params, target)
        return blocked

    try:
        if action == "move":
            current = _normal_window_rect(target["hwnd"])
            result = winapi.set_window_bounds(
                target["hwnd"], prepared["x"], prepared["y"], current["width"], current["height"]
            )
        elif action == "resize":
            current = _normal_window_rect(target["hwnd"])
            result = winapi.set_window_bounds(
                target["hwnd"], current["x"], current["y"], prepared["width"], prepared["height"]
            )
        elif action == "set_bounds":
            result = winapi.set_window_bounds(
                target["hwnd"], prepared["x"], prepared["y"], prepared["width"], prepared["height"]
            )
        elif action in ("minimize", "maximize", "restore"):
            result = winapi.set_window_state(target["hwnd"], action)
        elif action == "close":
            result = winapi.close_window(target["hwnd"])
        else:  # tile
            tile = prepared["tile"]
            if tile == "maximize":
                area = winapi.work_area(prepared["monitor"])
                result = winapi.set_window_state(target["hwnd"], "maximize")
                applied = result["window"]["rect"]
                requested = area["work_area"]
                delta = {
                    key: applied[key] - requested[key]
                    for key in ("x", "y", "width", "height")
                }
                result.update(
                    {
                        "tile": tile,
                        "work_area": area["work_area"],
                        "monitor": area["index"],
                        "requested_bounds": requested,
                        "applied_bounds": applied,
                        "delta": delta,
                        "clamped": any(abs(value) > 4 for value in delta.values()),
                    }
                )
            else:
                area = winapi.work_area(prepared["monitor"])
                bounds = winapi.tile_bounds(area["work_area"], tile)
                result = winapi.set_window_bounds(
                    target["hwnd"], bounds["x"], bounds["y"], bounds["width"], bounds["height"]
                )
                result["tile"] = tile
                result["work_area"] = area["work_area"]
                result["monitor"] = area["index"]
    except ValueError as exc:
        LOG.write("manage_window", "error", params, target, error=str(exc))
        return _error("invalid_args", str(exc), window=target)
    except Exception as exc:  # noqa: BLE001
        LOG.write("manage_window", "error", params, target, error=repr(exc))
        return _error("manage_window_failed", f"窗口操作失败：{exc}", window=target)

    LOG.write(
        "manage_window", "end", params, result.get("window") or target,
        outcome=action,
    )
    return _dump({"ok": True, "action": action, **result})


def hover(
    x: int,
    y: int,
    duration_ms: int = 500,
    hwnd: int | None = None,
    confirm_token: str | None = None,
) -> str:
    params = {"x": x, "y": y, "duration_ms": duration_ms, "hwnd": hwnd}
    LOG.write("hover", "start", params)
    x_value, y_value = _as_int(x), _as_int(y)
    duration_value = _as_int(duration_ms)
    if x_value is None or y_value is None:
        return _error("invalid_args", "x、y 必须是整数物理像素。")
    if duration_value is None or not 0 <= duration_value <= 10000:
        return _error("invalid_duration", "duration_ms 必须在 0~10000 之间。")
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    try:
        screen_x, screen_y = winapi.resolve_click_point(x_value, y_value, hwnd)
        target = winapi.window_at_point(screen_x, screen_y)
    except ValueError as exc:
        return _error("invalid_coordinates", str(exc))
    if hwnd is not None and (target is None or int(target["hwnd"]) != int(hwnd)):
        return _error(
            "target_mismatch",
            "请求的 hwnd 与屏幕落点实际顶层窗口不一致；hwnd 不能替代真实命中对象，已拒绝。",
            requested_hwnd=hwnd,
            actual_window=target,
        )
    blocked = _gate("hover", params, target, confirm_token)
    if blocked:
        LOG.write("hover", "pending_confirmation", params, target)
        return blocked
    try:
        result = winapi.hover(
            x_value, y_value, duration_value, hwnd,
            expected_hwnd=None if target is None else int(target["hwnd"]),
        )
    except ValueError as exc:
        LOG.write("hover", "blocked", params, target, outcome="target_changed")
        return _error("target_changed", str(exc), window=target)
    except Exception as exc:  # noqa: BLE001
        LOG.write("hover", "error", params, target, error=repr(exc))
        return _error("hover_failed", f"悬停失败：{exc}")
    LOG.write("hover", "end", params, result.get("target"), outcome=f"{duration_value}ms")
    return _dump({"ok": True, **result})


def drag(
    from_x: int,
    from_y: int,
    to_x: int,
    to_y: int,
    button: str = "left",
    steps: int = 12,
    hold_ms_before: int = 50,
    hold_ms_after: int = 50,
    hwnd: int | None = None,
    confirm_token: str | None = None,
) -> str:
    params = {
        "from_x": from_x, "from_y": from_y, "to_x": to_x, "to_y": to_y,
        "button": button, "steps": steps,
        "hold_ms_before": hold_ms_before, "hold_ms_after": hold_ms_after, "hwnd": hwnd,
    }
    LOG.write("drag", "start", params)
    values = [_as_int(from_x), _as_int(from_y), _as_int(to_x), _as_int(to_y)]
    if any(value is None for value in values):
        return _error("invalid_args", "from_x/from_y/to_x/to_y 必须是整数物理像素。")
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    if not isinstance(button, str) or button.lower() not in ("left", "right", "middle"):
        return _error("invalid_button", "button 必须是 left、right 或 middle。")
    steps_value = _as_int(steps)
    hold_before_value = _as_int(hold_ms_before)
    hold_after_value = _as_int(hold_ms_after)
    if steps_value is None or not 2 <= steps_value <= 200:
        return _error("invalid_steps", "steps 必须在 2~200 之间。")
    if hold_before_value is None or not 0 <= hold_before_value <= 5000:
        return _error("invalid_hold", "hold_ms_before 必须在 0~5000 之间。")
    if hold_after_value is None or not 0 <= hold_after_value <= 5000:
        return _error("invalid_hold", "hold_ms_after 必须在 0~5000 之间。")
    try:
        screen_from = winapi.resolve_click_point(values[0], values[1], hwnd)
        winapi.resolve_click_point(values[2], values[3], hwnd)
        target = winapi.window_at_point(*screen_from)
    except ValueError as exc:
        return _error("invalid_coordinates", str(exc))
    if hwnd is not None and (target is None or int(target["hwnd"]) != int(hwnd)):
        return _error(
            "target_mismatch",
            "请求的 hwnd 与拖拽起点实际顶层窗口不一致；hwnd 不能替代真实命中对象，已拒绝。",
            requested_hwnd=hwnd,
            actual_window=target,
        )
    blocked = _gate("drag", params, target, confirm_token)
    if blocked:
        LOG.write("drag", "pending_confirmation", params, target)
        return blocked
    try:
        result = winapi.drag(
            values[0], values[1], values[2], values[3],
            button=button.lower(),
            steps=steps_value,
            hold_ms_before=hold_before_value,
            hold_ms_after=hold_after_value,
            hwnd=hwnd,
            expected_hwnd=None if target is None else int(target["hwnd"]),
        )
    except ValueError as exc:
        return _error("target_changed", str(exc), window=target)
    except Exception as exc:  # noqa: BLE001
        LOG.write("drag", "error", params, target, error=repr(exc))
        return _error("drag_failed", f"拖拽失败：{exc}")
    if result.get("aborted_blocked_window"):
        LOG.write("drag", "blocked", params, result.get("blocked_window"))
        return _dump(
            {
                "ok": False,
                "error": "aborted_blocked_window",
                "error_code": "aborted_blocked_window",
                "message": "拖拽途中落点进入禁止操作窗口，已立即抬起按键并中止。",
                **result,
            }
        )
    LOG.write("drag", "end", params, result.get("target"), outcome=f"{result['steps']} steps")
    return _dump({"ok": True, **result})


def _target_matches(
    info: dict[str, Any] | None,
    hwnd: int | None,
    process: str | None,
    title: str | None,
) -> bool:
    if info is None:
        return False
    if hwnd is not None:
        return info["hwnd"] == hwnd
    if process and winapi._normalize_process(info["process"]) != winapi._normalize_process(process):
        return False
    if title and title.casefold() not in info["title"].casefold():
        return False
    return True


def wait(
    condition: str,
    timeout_ms: int = 10000,
    poll_ms: int = 200,
    process: str | None = None,
    title: str | None = None,
    hwnd: int | None = None,
    stable_rect: dict[str, Any] | None = None,
    stable_frames: int = 3,
    stable_threshold: float = 0.01,
    confirm_token: str | None = None,
) -> str:
    del confirm_token  # wait 只读，永不走确认门；保留参数仅为统一调用习惯。
    conditions = {
        "timeout", "window_exists", "window_gone", "title_contains",
        "foreground_is", "screenshot_stable",
    }
    if not isinstance(condition, str) or condition.strip().lower() not in conditions:
        return _error("invalid_condition", f"condition 必须是：{', '.join(sorted(conditions))}。")
    condition = condition.strip().lower()
    timeout_value = _as_int(timeout_ms)
    poll_value = _as_int(poll_ms)
    if timeout_value is None or not 0 <= timeout_value <= 60000:
        return _error("invalid_timeout", "timeout_ms 必须在 0~60000 之间。")
    if poll_value is None or not 50 <= poll_value <= 5000:
        return _error("invalid_poll", "poll_ms 必须在 50~5000 之间。")
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    if process is not None and not isinstance(process, str):
        return _error("invalid_process", "process 必须是字符串。")
    if title is not None and not isinstance(title, str):
        return _error("invalid_title", "title 必须是字符串。")

    params = {
        "condition": condition, "timeout_ms": timeout_value, "poll_ms": poll_value,
        "process": process, "title": title, "hwnd": hwnd,
        "stable_rect": stable_rect, "stable_frames": stable_frames,
        "stable_threshold": stable_threshold,
    }
    LOG.write("wait", "start", params)
    started = time.monotonic()
    deadline = started + timeout_value / 1000.0

    def elapsed() -> int:
        return int(round((time.monotonic() - started) * 1000))

    def find_target() -> dict[str, Any] | None:
        if hwnd is not None:
            return winapi.window_info(hwnd)
        if process or title:
            matches = winapi.find_windows(process=process, title=title)
            return matches[0] if matches else None
        return None

    if condition == "timeout":
        time.sleep(timeout_value / 1000.0)
        return _dump({"ok": True, "condition": condition, "elapsed_ms": elapsed(), "timed_out": False})

    if condition in ("window_exists", "window_gone", "title_contains", "foreground_is"):
        if hwnd is None and not process and not title:
            return _error("invalid_args", "该条件需要 hwnd、process、title 至少一个。")
        if condition == "title_contains" and not title:
            return _error("invalid_args", "title_contains 需要 title 关键字。")

        def check() -> tuple[bool, dict[str, Any] | None]:
            if condition == "window_exists":
                found = find_target()
                return bool(found), found
            if condition == "window_gone":
                return find_target() is None, None
            if condition == "title_contains":
                found = find_target()
                matched = bool(found and title and title.casefold() in found["title"].casefold())
                return matched, found
            foreground = winapi.foreground_info()
            return _target_matches(foreground, hwnd, process, title), foreground

        while True:
            matched, found = check()
            if matched:
                payload = {
                    "ok": True, "condition": condition, "elapsed_ms": elapsed(), "timed_out": False,
                }
                if found:
                    payload["window"] = found
                LOG.write("wait", "end", params, found, outcome=condition)
                return _dump(payload)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                LOG.write("wait", "timeout", params, outcome=condition)
                return _dump(
                    {
                        "ok": False, "timed_out": True, "condition": condition,
                        "elapsed_ms": elapsed(), "message": f"{timeout_value}ms 内条件未满足。",
                    }
                )
            time.sleep(min(poll_value / 1000.0, remaining))

    # screenshot_stable
    frames_value = _as_int(stable_frames)
    if frames_value is None or not 1 <= frames_value <= 20:
        return _error("invalid_stable_frames", "stable_frames 必须在 1~20 之间。")
    try:
        threshold_value = float(stable_threshold)
    except (TypeError, ValueError):
        return _error("invalid_threshold", "stable_threshold 必须是 0~1 之间的数字。")
    if not 0 <= threshold_value <= 1:
        return _error("invalid_threshold", "stable_threshold 必须是 0~1 之间的数字。")

    try:
        if stable_rect is not None:
            if not isinstance(stable_rect, dict):
                raise ValueError("stable_rect 必须是 {x,y,width,height} 对象。")
            region = {key: _as_int(stable_rect.get(key)) for key in ("x", "y", "width", "height")}
            if any(value is None for value in region.values()):
                raise ValueError("stable_rect 需要整数 x、y、width、height。")
        elif hwnd is not None:
            info = winapi.window_info(hwnd)
            if info is None:
                return _error("window_not_found", "窗口句柄无效或窗口已关闭。")
            if info["minimized"]:
                return _error("window_minimized", "窗口已最小化，先还原后再等待画面稳定。")
            region = winapi.client_metrics(hwnd)
        else:
            metrics = winapi.screen_metrics()
            region = {
                "x": metrics["x"], "y": metrics["y"],
                "width": metrics["width"], "height": metrics["height"],
            }
    except ValueError as exc:
        return _error("invalid_region", str(exc))

    previous_raw: bytes | None = None
    stable_count = 0
    frames_seen = 0
    last_hash = ""
    while True:
        try:
            image, _meta = winapi.grab_image(region=region)
        except Exception as exc:  # noqa: BLE001
            return _error("screenshot_failed", f"稳定度采样失败：{exc}")
        digest, raw = winapi.image_fingerprint(image)
        frames_seen += 1
        last_hash = digest
        if previous_raw is None:
            stable_count = 1
        else:
            ratio = winapi.image_diff_ratio(previous_raw, raw)
            stable_count = stable_count + 1 if ratio <= threshold_value else 1
        previous_raw = raw
        if stable_count >= frames_value:
            LOG.write("wait", "end", params, outcome=f"stable after {frames_seen} frames")
            return _dump(
                {
                    "ok": True, "condition": condition, "elapsed_ms": elapsed(),
                    "timed_out": False, "frames": frames_seen,
                    "stable_frames": stable_count, "threshold": threshold_value,
                    "last_hash": last_hash, "region": region,
                }
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            LOG.write("wait", "timeout", params, outcome=condition)
            return _dump(
                {
                    "ok": False, "timed_out": True, "condition": condition,
                    "elapsed_ms": elapsed(), "frames": frames_seen,
                    "stable_frames": stable_count, "threshold": threshold_value,
                    "last_hash": last_hash, "region": region,
                    "message": f"{timeout_value}ms 内画面未稳定。",
                }
            )
        time.sleep(min(poll_value / 1000.0, remaining))


def clipboard(
    action: str,
    text: str | None = None,
    format: str = "text",
    backup: bool = True,
    confirm_token: str | None = None,
) -> str:
    if not isinstance(action, str) or action.strip().lower() not in ("get", "set", "clear", "restore"):
        return _error("invalid_action", "action 必须是 get、set、clear 或 restore。")
    action = action.strip().lower()
    if format != "text":
        return _error("unsupported_format", "本批只支持 format=text（Unicode 文本）。")
    params = {"action": action, "text": text, "format": format, "backup": bool(backup)}
    LOG.write(
        "clipboard", "start",
        {"action": action, "format": format, "backup": bool(backup), "chars": len(text or "")},
    )

    if action == "get":
        try:
            value = clipboard_win.get_text()
        except Exception as exc:  # noqa: BLE001
            return _error("clipboard_read_failed", f"读取剪贴板失败：{exc}")
        if value is None:
            return _dump({"ok": True, "empty": True, "text": "", "length": 0, "truncated": False})
        limit_bytes = 8192
        encoded = value.encode("utf-8")
        if len(encoded) > limit_bytes:
            clipped = encoded[:limit_bytes].decode("utf-8", errors="ignore")
            truncated = True
        else:
            clipped = value
            truncated = False
        payload = {
            "ok": True, "empty": False, "text": clipped,
            "length": len(value), "returned_length": len(clipped), "truncated": truncated,
        }
        LOG.write("clipboard", "end", {"action": "get"}, outcome=f"{len(value)} chars")
        return _dump(payload)

    if action == "set" and (not isinstance(text, str) or text == ""):
        return _error("invalid_text", "set 需要非空字符串 text。")
    blocked = _gate(f"clipboard.{action}", params, None, confirm_token)
    if blocked:
        LOG.write(
            "clipboard", "pending_confirmation",
            {"action": action, "format": format, "backup": bool(backup), "chars": len(text or "")},
        )
        return blocked

    try:
        if action == "set":
            result = clipboard_win.set_text(text, backup=bool(backup))
        elif action == "clear":
            result = clipboard_win.clear(backup=bool(backup))
        else:
            result = clipboard_win.restore()
    except clipboard_win.ClipboardError as exc:
        LOG.write("clipboard", "error", params, error=str(exc))
        code = "clipboard_backup_failed" if "备份" in str(exc) else "clipboard_write_failed"
        return _error(code, f"剪贴板操作失败：{exc}")
    except Exception as exc:  # noqa: BLE001
        LOG.write("clipboard", "error", params, error=repr(exc))
        return _error("clipboard_write_failed", f"剪贴板写入失败：{exc}")
    if action == "restore" and not result.get("restored"):
        LOG.write("clipboard", "conflict", {"action": action}, outcome=str(result.get("error_code")))
        return _error(
            str(result.get("error_code") or "no_backup"),
            str(result.get("message") or "没有可恢复的剪贴板快照。"),
            status="clipboard_conflict" if result.get("conflict") else "no_backup",
            details=result,
        )
    LOG.write("clipboard", "end", {"action": action, "format": format}, outcome=action)
    return _dump({"ok": True, "action": action, **result})


def launch_app(
    path: str,
    args: str | None = None,
    workdir: str | None = None,
    wait_window_ms: int = 5000,
    as_admin: bool = False,
    confirm_token: str | None = None,
) -> str:
    if as_admin:
        return _error("as_admin_not_supported", "本批固定 as_admin=false，不支持提权启动。")
    if not isinstance(path, str) or not path.strip():
        return _error("invalid_path", "path 必须是非空字符串。")
    if args is not None and not isinstance(args, str):
        return _error("invalid_args", "args 必须是字符串。")
    if workdir is not None and not isinstance(workdir, str):
        return _error("invalid_workdir", "workdir 必须是字符串。")
    wait_value = _as_int(wait_window_ms)
    if wait_value is None or not 0 <= wait_value <= 60000:
        return _error("invalid_wait", "wait_window_ms 必须在 0~60000 之间。")
    params = {"path": path, "args": args, "workdir": workdir, "wait_window_ms": wait_value, "as_admin": False}
    LOG.write("launch_app", "start", params)
    blocked = _gate("launch_app", params, None, confirm_token)
    if blocked:
        LOG.write("launch_app", "pending_confirmation", params)
        return blocked
    try:
        result = launcher.launch(path, args=args, workdir=workdir, wait_window_ms=wait_value)
    except PermissionError as exc:
        LOG.write("launch_app", "blocked", params, error=str(exc))
        return _error("blocked_launch", str(exc))
    except ValueError as exc:
        LOG.write("launch_app", "error", params, error=str(exc))
        return _error("invalid_path", str(exc))
    except Exception as exc:  # noqa: BLE001
        LOG.write("launch_app", "error", params, error=repr(exc))
        return _error("launch_failed", f"启动失败：{exc}")
    LOG.write("launch_app", "end", params, result.get("window"), outcome=str(result.get("pid")))
    if wait_value > 0 and result.get("window") is None:
        result["message"] = "已启动，但在 wait_window_ms 内没有匹配到新窗口；可能复用了已有进程。"
    return _dump({"ok": True, **result})


def find_text(
    text: str,
    hwnd: int | None = None,
    region: dict[str, Any] | None = None,
    lang: str = "chi_sim+eng",
    match: str = "contains",
    max_results: int = 10,
    confirm_token: str | None = None,
) -> str:
    del confirm_token  # 只读；真正点击仍由 click 的确认门负责。
    if not isinstance(text, str) or not text.strip():
        return _error("invalid_text", "text 必须是非空字符串。")
    if not isinstance(lang, str) or not lang.strip():
        return _error("invalid_lang", "lang 必须是非空字符串。")
    if match not in ("exact", "contains"):
        return _error("invalid_match", "match 必须是 exact 或 contains。")
    limit = _as_int(max_results)
    if limit is None or not 1 <= limit <= 50:
        return _error("invalid_max_results", "max_results 必须在 1~50 之间。")
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    params = {
        "text": text, "hwnd": hwnd, "region": region, "lang": lang,
        "match": match, "max_results": limit,
    }
    LOG.write("find_text", "start", params)

    if hwnd is not None:
        info = winapi.window_info(hwnd)
        if info is None:
            return _error("invalid_hwnd", "窗口句柄无效或窗口已关闭。")
        reason = security.forbidden_reason(info)
        if reason:
            LOG.write("find_text", "blocked", params, info)
            return _error("forbidden_window", reason, window=info)

    if region is not None and not isinstance(region, dict):
        return _error("invalid_region", "region 必须是 {x,y,width,height} 对象。")
    try:
        if region is not None:
            parsed_region = {key: _as_int(region.get(key)) for key in ("x", "y", "width", "height")}
            if any(value is None for value in parsed_region.values()):
                raise ValueError("region 需要整数 x、y、width、height。")
            capture_rect = parsed_region
        elif hwnd is not None:
            capture_rect = winapi.client_metrics(hwnd)
        else:
            metrics = winapi.screen_metrics()
            capture_rect = {
                "x": metrics["x"], "y": metrics["y"],
                "width": metrics["width"], "height": metrics["height"],
            }
        forbidden_hits = security.forbidden_windows(capture_rect)
        if forbidden_hits:
            LOG.write("find_text", "blocked", params, None)
            return _error(
                "forbidden_window",
                "OCR 区域与受保护窗口相交，已拒绝；请先关闭或移动受保护窗口。",
                windows=forbidden_hits,
            )
        if region is not None:
            image, metadata = winapi.grab_image(region=parsed_region)
        else:
            image, metadata = winapi.grab_image(hwnd=hwnd)
    except ValueError as exc:
        return _error("invalid_region", str(exc))
    except Exception as exc:  # noqa: BLE001
        return _error("screenshot_failed", f"OCR 截图失败：{exc}")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    recognized = ocr.recognize(buffer.getvalue(), lang)
    if not recognized.get("ok"):
        LOG.write("find_text", "error", params, error=recognized.get("error"))
        code = recognized.get("error") or "ocr_unavailable"
        extra = {"install_hint": recognized.get("install_hint")} if code == "ocr_unavailable" else {}
        return _error(code, recognized.get("message") or "OCR 引擎不可用。", **extra)

    matches = ocr.find_matches(
        recognized.get("lines") or [], text, match=match, max_results=limit
    )
    engine_used = recognized.get("engine")
    if any(char.isascii() and char.isalnum() for char in text):
        # 拉丁字符容易被光标/抗锯齿漏识别（例如 ABC 只剩 AB）；用 Tesseract eng
        # 补词框后再匹配一次，顺带提供 Windows OCR 没有的置信度。
        merged_lines, supplement = ocr.supplement_latin(buffer.getvalue(), recognized.get("lines") or [])
        if supplement:
            merged_matches = ocr.find_matches(merged_lines, text, match=match, max_results=limit)
            if merged_matches:
                matches = merged_matches
                engine_used = f"{engine_used}+{supplement}"
    origin = metadata["origin"]
    scale = float(metadata.get("scale") or 1.0)
    results = []
    for hit in matches:
        rect = hit["rect"]
        center_x = int(round(origin["x"] + hit["cx"] / scale))
        center_y = int(round(origin["y"] + hit["cy"] / scale))
        screen_rect = {
            "x": int(round(origin["x"] + rect["x"] / scale)),
            "y": int(round(origin["y"] + rect["y"] / scale)),
            "width": int(round(rect["width"] / scale)),
            "height": int(round(rect["height"] / scale)),
        }
        results.append(
            {
                "text": hit["text"],
                "confidence": hit["confidence"],
                "cx": center_x,
                "cy": center_y,
                "center": {"x": center_x, "y": center_y},
                "rect": screen_rect,
                "image_rect": rect,
                **(
                    {"confidence_note": "Windows OCR 不提供置信度；Tesseract 补词框时才有数值。"}
                    if hit["confidence"] is None
                    else {}
                ),
            }
        )

    LOG.write(
        "find_text", "end", params,
        outcome=f"{len(results)} hits / {len(recognized.get('lines') or [])} lines",
    )
    return _dump(
        {
            "ok": True,
            "count": len(results),
            "results": results,
            "engine": engine_used,
            "ocr_lang": recognized.get("lang"),
            "coordinate_space": "screen-physical-pixels",
            "coordinate_formula": "screen = origin + screenshot_coordinate / scale",
            "origin": origin,
            "scale": scale,
            "image": {
                "mode": metadata["mode"],
                "hwnd": metadata.get("hwnd"),
                "width": metadata["width"],
                "height": metadata["height"],
            },
            "match": match,
            "query": text,
        }
    )


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
        "text": {"type": "string", "maxLength": 100000, "description": "要输入的文本，支持中文、换行与制表符。"},
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
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
}
_MANAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["move", "resize", "set_bounds", "minimize", "maximize", "restore", "close", "tile", "get_work_area"],
            "description": "窗口操作；get_work_area 只读、不走确认门。",
        },
        "hwnd": {"type": ["integer", "null"], "default": None, "description": "目标窗口句柄，优先级最高。"},
        "process": {"type": ["string", "null"], "default": None, "description": "进程名，可带或不带 .exe。"},
        "title": {"type": ["string", "null"], "default": None, "description": "标题关键字（子串、不区分大小写）。"},
        "x": {"type": ["integer", "null"], "default": None, "description": "物理像素 X；move 必填，set_bounds 必填。"},
        "y": {"type": ["integer", "null"], "default": None},
        "width": {"type": ["integer", "null"], "default": None},
        "height": {"type": ["integer", "null"], "default": None},
        "tile": {
            "type": ["string", "null"],
            "enum": ["left_half", "right_half", "top_left", "top_right", "bottom_left", "bottom_right", "maximize", None],
            "default": None,
            "description": "并排预设，相对工作区（排除任务栏）。",
        },
        "monitor": {"type": "integer", "default": 0, "description": "显示器索引，默认 0（主屏）。"},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["action"],
}
_HOVER_SCHEMA = {
    "type": "object",
    "properties": {
        "x": {"type": "integer", "description": "物理像素 X；有 hwnd 时为客户区相对 X。"},
        "y": {"type": "integer", "description": "物理像素 Y；有 hwnd 时为客户区相对 Y。"},
        "duration_ms": {"type": "integer", "default": 500, "minimum": 0, "maximum": 10000},
        "hwnd": {"type": ["integer", "null"], "default": None},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["x", "y"],
}
_DRAG_SCHEMA = {
    "type": "object",
    "properties": {
        "from_x": {"type": "integer", "description": "起点物理像素 X；有 hwnd 时为客户区相对 X。"},
        "from_y": {"type": "integer"},
        "to_x": {"type": "integer"},
        "to_y": {"type": "integer"},
        "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
        "steps": {"type": "integer", "default": 12, "minimum": 2, "maximum": 200, "description": "中间插值步数。"},
        "hold_ms_before": {"type": "integer", "default": 50, "minimum": 0, "maximum": 5000},
        "hold_ms_after": {"type": "integer", "default": 50, "minimum": 0, "maximum": 5000},
        "hwnd": {"type": ["integer", "null"], "default": None},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["from_x", "from_y", "to_x", "to_y"],
}
_WAIT_SCHEMA = {
    "type": "object",
    "properties": {
        "condition": {
            "type": "string",
            "enum": ["timeout", "window_exists", "window_gone", "title_contains", "foreground_is", "screenshot_stable"],
        },
        "timeout_ms": {"type": "integer", "default": 10000, "minimum": 0, "maximum": 60000},
        "poll_ms": {"type": "integer", "default": 200, "minimum": 50, "maximum": 5000},
        "process": {"type": ["string", "null"], "default": None},
        "title": {"type": ["string", "null"], "default": None},
        "hwnd": {"type": ["integer", "null"], "default": None},
        "stable_rect": {
            "type": ["object", "null"],
            "default": None,
            "description": "screenshot_stable 的区域（屏幕物理像素）；省略时用 hwnd 客户区或整屏。",
            "properties": {
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "width": {"type": "integer"}, "height": {"type": "integer"},
            },
            "required": ["x", "y", "width", "height"],
        },
        "stable_frames": {"type": "integer", "default": 3, "minimum": 1, "maximum": 20},
        "stable_threshold": {"type": "number", "default": 0.01, "minimum": 0, "maximum": 1},
    },
    "required": ["condition"],
}
_CLIPBOARD_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["get", "set", "clear", "restore"]},
        "text": {"type": ["string", "null"], "default": None, "maxLength": 100000, "description": "set 时必填。"},
        "format": {"type": "string", "default": "text", "description": "本批只支持 text。"},
        "backup": {"type": "boolean", "default": True, "description": "set/clear 前保存文本快照供 restore。"},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["action"],
}
_LAUNCH_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "maxLength": 32767, "description": "绝对路径、文档路径或 URI（ms-settings:、shell: 等）。"},
        "args": {"type": ["string", "null"], "default": None, "maxLength": 32767},
        "workdir": {"type": ["string", "null"], "default": None, "maxLength": 32767},
        "wait_window_ms": {"type": "integer", "default": 5000, "minimum": 0, "maximum": 60000},
        "as_admin": {"type": "boolean", "default": False, "description": "本批固定 false；true 直接拒绝。"},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["path"],
}
_FIND_TEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "maxLength": 2000, "description": "要找的文字。"},
        "hwnd": {"type": ["integer", "null"], "default": None, "description": "只搜该窗口客户区。"},
        "region": {
            "type": ["object", "null"],
            "default": None,
            "description": "屏幕物理像素区域；省略时用 hwnd 客户区或整屏。",
            "properties": {
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "width": {"type": "integer"}, "height": {"type": "integer"},
            },
            "required": ["x", "y", "width", "height"],
        },
        "lang": {"type": "string", "default": "chi_sim+eng"},
        "match": {"type": "string", "enum": ["exact", "contains"], "default": "contains"},
        "max_results": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
    },
    "required": ["text"],
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
    {
        "name": "manage_window",
        "description": "窗口管理：move/resize/set_bounds/minimize/maximize/restore/close/tile，以及只读的 get_work_area。坐标与 tile 均用物理像素/工作区；set_bounds 与 tile 会回读 applied_bounds，被系统钳制时 clamped=true。close 只发 WM_CLOSE，不杀进程，出现未保存对话框时返回 close_pending_dialog=true。写操作走确认门，get_work_area 不走。",
        "inputSchema": _MANAGE_SCHEMA,
    },
    {
        "name": "hover",
        "description": "把鼠标光标移到物理像素坐标并停留 duration_ms（默认 500，上限 10000），不按键；有 hwnd 时坐标相对客户区。走确认门。",
        "inputSchema": _HOVER_SCHEMA,
    },
    {
        "name": "drag",
        "description": "鼠标拖拽：按下起点、按 steps 插值移动到终点、再松开；支持 left/right/middle，hold_ms_before/after 默认 50。途中落点进入禁止窗口会立即抬键中止并返回 aborted_blocked_window。走确认门。",
        "inputSchema": _DRAG_SCHEMA,
    },
    {
        "name": "wait",
        "description": "只读等待：timeout/window_exists/window_gone/title_contains/foreground_is/screenshot_stable。超时返回 ok=false、timed_out=true，不抛异常；screenshot_stable 只返回哈希摘要，不返回截图。不走确认门。",
        "inputSchema": _WAIT_SCHEMA,
    },
    {
        "name": "clipboard",
        "description": "剪贴板文本读写：get 返回文本（默认截断 8KB）；set 写入文本并默认保存备份；clear 清空；restore 恢复本会话最近一次 set/clear 前的文本。get 不走确认门，set/clear/restore 走确认门。",
        "inputSchema": _CLIPBOARD_SCHEMA,
    },
    {
        "name": "launch_app",
        "description": "用 ShellExecuteEx 启动应用/文档/URI（绝对路径或明确 scheme），可等待主窗口出现并返回 hwnd。拒绝相对路径、as_admin=true、脚本宿主（powershell/cmd/wscript/cscript/mshta/reg 等）。走确认门。",
        "inputSchema": _LAUNCH_SCHEMA,
    },
    {
        "name": "find_text",
        "description": "OCR 找字：在整屏、指定窗口客户区或 region 中查找文字，返回每条命中的 confidence、屏幕物理像素中心点 cx/cy 与外接矩形，可直接传给 click。Windows OCR 优先，Tesseract 回退；引擎不可用返回 ocr_unavailable。只读，不走确认门。",
        "inputSchema": _FIND_TEXT_SCHEMA,
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
    "manage_window": manage_window,
    "hover": hover,
    "drag": drag,
    "wait": wait,
    "clipboard": clipboard,
    "launch_app": launch_app,
    "find_text": find_text,
}


TOOL_SCHEMAS = {tool["name"]: tool["inputSchema"] for tool in TOOLS}


def _payload_from_result(result: Any) -> dict[str, Any] | None:
    """从工具返回值里取出 JSON 文本 payload，用于判断 isError。"""
    text = None
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                break
    elif isinstance(result, str):
        text = result
    if not isinstance(text, str):
        return None
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _result_is_error(result: Any) -> bool:
    payload = _payload_from_result(result)
    if payload is None:
        return False
    if payload.get("status") in ("confirmation_required", "timed_out", "close_pending_dialog"):
        return False
    if payload.get("timed_out") is True:
        return False
    return payload.get("ok") is False


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {
            "content": [{"type": "text", "text": _error("unknown_tool", f"未知工具：{name}")}],
            "isError": True,
        }
    schema = TOOL_SCHEMAS.get(name)
    if schema is None:
        return {
            "content": [{"type": "text", "text": _error("unknown_tool", f"未知工具：{name}")}],
            "isError": True,
        }
    validation_errors = schema_validate.validate(schema, arguments)
    if validation_errors:
        return {
            "content": [
                {
                    "type": "text",
                    "text": _error(
                        "invalid_arguments",
                        "参数校验失败，操作未执行。",
                        details=validation_errors,
                    ),
                }
            ],
            "isError": True,
        }
    allowed = {parameter.name for parameter in inspect.signature(function).parameters.values()}
    kwargs = {key: value for key, value in arguments.items() if key in allowed}
    try:
        result = function(**kwargs)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        result = _error("tool_exception", f"{name} 执行异常：{exc}")
    content = result if isinstance(result, list) else [{"type": "text", "text": str(result)}]
    return {"content": content, "isError": _result_is_error(result)}


def _jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def _valid_request_id(value: Any) -> bool:
    return isinstance(value, (str, int)) and not isinstance(value, bool)


def _handle(message: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    if message.get("jsonrpc") != "2.0":
        return _jsonrpc_error(message.get("id"), -32600, "Invalid Request: jsonrpc 必须是 \"2.0\"。")
    method = message.get("method")
    if not isinstance(method, str) or not method:
        return _jsonrpc_error(message.get("id"), -32600, "Invalid Request: method 必须是非空字符串。")

    request_id = message.get("id")
    has_id = "id" in message
    if has_id and not _valid_request_id(request_id):
        return _jsonrpc_error(None, -32600, "Invalid Request: id 必须是字符串或整数。")
    notification = not has_id

    params = message.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        if notification:
            return None
        return _jsonrpc_error(request_id, -32602, "Invalid params: params 必须是对象。")

    if notification:
        if method == "notifications/initialized":
            state["initialized"] = True
        elif method == "notifications/cancelled":
            state["cancel_requested"] = True
        return None

    if method == "initialize":
        requested = params.get("protocolVersion")
        protocol = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        state["initialized"] = True
        state["protocol"] = protocol
        result = {
            "protocolVersion": protocol,
            "supportedProtocolVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": VERSION},
            "instructions": INSTRUCTIONS,
        }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if not state.get("initialized"):
        return _jsonrpc_error(request_id, -32002, "Server not initialized: 先调用 initialize。")

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not name:
            return _jsonrpc_error(request_id, -32602, "Invalid params: tools/call 需要 name 字符串。")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return _jsonrpc_error(request_id, -32602, "Invalid params: arguments 必须是对象。")
        return {"jsonrpc": "2.0", "id": request_id, "result": _call_tool(name, arguments)}
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


class _JsonLimits:
    @staticmethod
    def parse_int(text: str) -> int:
        if len(text) > MAX_JSON_INT_DIGITS:
            raise ValueError(f"整数超过 {MAX_JSON_INT_DIGITS} 位")
        return int(text)

    @staticmethod
    def parse_float(text: str) -> float:
        value = float(text)
        if len(text) > 256 or value != value or value in (float("inf"), float("-inf")):
            raise ValueError("浮点数超出允许范围")
        return value

    @staticmethod
    def parse_constant(text: str) -> Any:
        raise ValueError(f"不允许的 JSON 常量：{text}")


def _json_depth_ok(text: str) -> bool:
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                return False
        elif char in "]}":
            depth -= 1
    return True


def _parse_frame(line: str) -> Any:
    if len(line.encode("utf-8")) > MAX_FRAME_BYTES:
        raise ValueError("帧超过大小上限")
    if not _json_depth_ok(line):
        raise ValueError(f"JSON 嵌套超过 {MAX_JSON_DEPTH} 层")
    return json.loads(
        line,
        parse_int=_JsonLimits.parse_int,
        parse_float=_JsonLimits.parse_float,
        parse_constant=_JsonLimits.parse_constant,
    )


def serve() -> int:
    state: dict[str, Any] = {"initialized": False, "protocol": None, "cancel_requested": False}
    while True:
        raw = sys.stdin.buffer.readline(MAX_FRAME_BYTES + 1)
        if not raw:
            break
        if len(raw) > MAX_FRAME_BYTES and not raw.endswith(b"\n"):
            # 丢弃超长帧剩余部分，保持后续帧可解析。
            while raw and not raw.endswith(b"\n"):
                raw = sys.stdin.buffer.readline(MAX_FRAME_BYTES + 1)
            response = _jsonrpc_error(None, -32700, "Parse error: 帧超过大小上限。")
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            continue
        try:
            line = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            response = _jsonrpc_error(None, -32700, f"Parse error: 无效 UTF-8：{exc}")
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            continue
        line = line.strip()
        if not line:
            continue
        try:
            message = _parse_frame(line)
        except (ValueError, TypeError, RecursionError, OverflowError, MemoryError) as exc:
            print(f"[juzi-win-dsh] 无效 JSON：{exc}", file=sys.stderr)
            response = _jsonrpc_error(None, -32700, f"Parse error: {exc}")
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(message, dict):
            response = _jsonrpc_error(None, -32600, "Invalid Request: 顶层必须是对象。")
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
            continue
        try:
            response = _handle(message, state)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            request_id = message.get("id") if _valid_request_id(message.get("id")) else None
            response = _jsonrpc_error(request_id, -32603, f"内部错误：{exc}")
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
