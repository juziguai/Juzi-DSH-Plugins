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

from contextvars import ContextVar
import base64
import inspect
import json
import os
import sys
import time
import traceback
from io import BytesIO
from typing import Any

import cdp
import focused_text
import clipboard_win
import launcher
import ocr
import schema_validate
import security
import system_control
import ui_tree
import winapi
from confirm import ConfirmationGate
from paste_text import paste_text
from runlog import RunLog

VERSION = "1.1.4"
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
_BATCH_ACTION = ContextVar("authorized_batch_action", default=None)
_ACTION_BATCH_CONFIRMED = ContextVar("authorized_action_batch", default=False)

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
    authorized = _BATCH_ACTION.get()
    if authorized is not None and authorized == (action, params, target):
        return None
    if _ACTION_BATCH_CONFIRMED.get():
        return None
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


def screenshot(
    hwnd: int | None = None,
    max_width: int = 1600,
    format: str = "png",
    quality: int = 82,
) -> list[dict[str, Any]]:
    fmt = (format or "png").strip().lower() if isinstance(format, str) else ""
    if fmt == "jpg":
        fmt = "jpeg"
    params = {"hwnd": hwnd, "max_width": max_width, "format": fmt, "quality": quality}
    LOG.write("screenshot", "start", params)
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return [{"type": "text", "text": _error("invalid_hwnd", "hwnd 必须是整数。")}]
        hwnd = parsed
    width = _as_int(max_width)
    if width is None:
        return [{"type": "text", "text": _error("invalid_max_width", "max_width 必须是整数。")}]
    if fmt not in ("png", "jpeg"):
        return [{"type": "text", "text": _error("invalid_format", "format 必须是 png 或 jpeg。")}]
    quality_value = _as_int(quality)
    if quality_value is None or not 40 <= quality_value <= 95:
        return [{"type": "text", "text": _error("invalid_quality", "quality 必须是 40~95 之间的整数。")}]

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
        if fmt == "png" and quality_value == 82:
            data, metadata = winapi.capture(max_width=width, hwnd=hwnd)
        else:
            data, metadata = winapi.capture(max_width=width, hwnd=hwnd, image_format=fmt, quality=quality_value)
    except Exception as exc:  # noqa: BLE001
        LOG.write("screenshot", "error", params, error=repr(exc))
        return [{"type": "text", "text": _error("screenshot_failed", f"截图失败：{exc}")}]

    target = winapi.window_info(hwnd) if hwnd is not None else None
    LOG.write(
        "screenshot", "end", params, target,
        outcome=f"{metadata['width']}x{metadata['height']} {fmt}",
    )
    mime_type = str(metadata.get("mime_type") or ("image/jpeg" if fmt == "jpeg" else "image/png"))
    text = _dump(
        {
            "ok": True,
            "message": "图像在下一个 content block；按 metadata 换算坐标。",
            **metadata,
        }
    )
    return [
        {"type": "text", "text": text},
        {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mimeType": mime_type},
    ]


def _attach_after_screenshot(
    payload: dict[str, Any],
    hwnd: int | None,
    after_wait_ms: int,
    screenshot_max_width: int,
    screenshot_format: str,
) -> list[dict[str, Any]]:
    wait_ms = max(0, min(5000, int(after_wait_ms)))
    if wait_ms > 0:
        time.sleep(wait_ms / 1000.0)
    shot = screenshot(hwnd=hwnd, max_width=screenshot_max_width, format=screenshot_format)
    shot_meta = _payload_from_result(shot)
    if shot_meta is not None:
        payload["after_screenshot"] = shot_meta
    blocks: list[dict[str, Any]] = [{"type": "text", "text": _dump(payload)}]
    for item in shot:
        if isinstance(item, dict) and item.get("type") == "image":
            blocks.append(item)
            break
    return blocks


def click(
    x: int,
    y: int,
    button: str = "left",
    double: bool = False,
    hwnd: int | None = None,
    confirm_token: str | None = None,
    after_screenshot: bool = False,
    after_wait_ms: int = 150,
    screenshot_max_width: int = 1280,
    screenshot_format: str = "jpeg",
) -> str | list[dict[str, Any]]:
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
    payload = {"ok": True, **result}
    if after_screenshot:
        return _attach_after_screenshot(payload, hwnd, after_wait_ms, screenshot_max_width, screenshot_format)
    return _dump(payload)


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


def input_batch(hwnd: int, actions: list, confirm_token: str | None = None) -> str:
    if _as_int(hwnd) is None or not isinstance(actions, list) or not 1 <= len(actions) <= 20:
        return _error("invalid_arguments", "批次须指定 hwnd 和 1~20 个输入动作。")
    target = winapi.foreground_info()
    if target is None or target["hwnd"] != hwnd:
        return _error("target_changed", "批次目标不在前台。")
    prepared = []
    for item in actions:
        if not isinstance(item, dict) or set(item) != {"tool", "arguments"}:
            return _error("invalid_arguments", "动作仅包含 tool 和 arguments。")
        name, args = item["tool"], item["arguments"]
        if name not in ("type_text", "press_keys") or not isinstance(args, dict):
            return _error("invalid_arguments", "批次仅支持 type_text 与 press_keys。")
        if "confirm_token" in args or "hwnd" in args:
            return _error("invalid_arguments", "动作继承批次目标与确认。")
        call_args = {**args, "hwnd": hwnd}
        if schema_validate.validate(TOOL_SCHEMAS[name], call_args):
            return _error("invalid_arguments", "批次动作参数不合法。")
        prepared.append((name, call_args))
    try:
        batch_focus = winapi.focused_hwnd()
    except Exception as exc:
        return _error("focus_unavailable", str(exc))
    blocked = _gate("input_batch", {"hwnd": hwnd, "actions": actions, "focus_hwnd": batch_focus}, target, confirm_token)
    if blocked:
        return blocked
    results = []
    for name, args in prepared:
        current = winapi.foreground_info()
        if current != target:
            return _error("target_changed", "批次目标已变化。", results=results)
        params = ({"text": args["text"], "method": args.get("method", "paste"), "hwnd": hwnd, "allow_unverified": args.get("allow_unverified", False)}
                  if name == "type_text" else {"keys": args["keys"].strip(), "hwnd": hwnd})
        if name == "type_text":
            try:
                focus = focused_text.read(hwnd)
                params["focus_id"] = focus["focus_id"]
            except Exception as exc:
                return _error("focused_text_unavailable", str(exc), results=results)
        if name == "press_keys":
            try:
                params["focus_hwnd"] = winapi.focused_hwnd()
            except Exception as exc:
                return _error("focus_unavailable", str(exc), results=results)
        token = _BATCH_ACTION.set((name, params, current))
        try:
            result = json.loads(TOOL_FUNCTIONS[name](**args))
        except Exception as exc:
            return _error("batch_stopped", str(exc), results=results, current_action=name)
        finally:
            _BATCH_ACTION.reset(token)
        results.append(result)
        if not result.get("ok") or result.get("status") == "dispatched_unverified":
            return _error("batch_stopped", "动作未成功，剩余动作未执行；勿自动重放已执行动作。", results=results)
    return _dump({"ok": True, "results": results})


_CDP_READ_ACTIONS = {"list_tabs", "inspect_page", "read_text"}
_CDP_WRITE_ACTIONS = {"open_url", "activate_tab", "close_tab", "click", "fill", "press_key"}
_ACTION_BATCH_READ_TOOLS = {"focus_window", "wait", "find_text", "screenshot", "inspect_ui", "read_screen_text"}
_ACTION_BATCH_WRITE_TOOLS = {"click", "hover", "scroll", "type_text", "press_keys"}
_ACTION_BATCH_ALLOWED = _ACTION_BATCH_READ_TOOLS | _ACTION_BATCH_WRITE_TOOLS | {"chrome_cdp"}


def action_batch(
    actions: list[dict[str, Any]],
    confirm_token: str | None = None,
) -> str | list[dict[str, Any]]:
    """一次调用顺序执行多步桌面操作（支持 focus_window / click / hover / scroll / wait / type_text / press_keys / find_text / screenshot）；任一步失败即中止。"""
    if not isinstance(actions, list) or not 1 <= len(actions) <= 20:
        return _error("invalid_arguments", "action_batch 须包含 1~20 个动作。")
    prepared: list[tuple[str, dict[str, Any]]] = []
    has_write = False
    for index, item in enumerate(actions):
        if not isinstance(item, dict) or set(item) != {"tool", "arguments"}:
            return _error("invalid_arguments", f"第 {index + 1} 个动作必须只包含 tool 和 arguments。")
        name, args = item["tool"], item["arguments"]
        if name not in _ACTION_BATCH_ALLOWED or not isinstance(args, dict):
            return _error("invalid_arguments", f"第 {index + 1} 个动作不支持：{name}。")
        if "confirm_token" in args:
            return _error("invalid_arguments", "子动作不得单独传 confirm_token，请统一在批次顶层传参。")
        errors = schema_validate.validate(TOOL_SCHEMAS[name], args)
        if errors:
            return _error("invalid_arguments", f"第 {index + 1} 个动作参数校验失败。", details=errors)
        if name in _ACTION_BATCH_WRITE_TOOLS or (name == "chrome_cdp" and args.get("action") in _CDP_WRITE_ACTIONS):
            has_write = True
        prepared.append((name, dict(args)))

    confirmed_batch = False
    if has_write and GATE.mode != "off":
        fg = winapi.foreground_info()
        if GATE.mode == "always" or confirm_token is not None:
            blocked = _gate("action_batch", {"actions": actions}, fg, confirm_token)
            if blocked:
                LOG.write("action_batch", "pending_confirmation", {"count": len(actions)}, fg)
                return blocked
            confirmed_batch = True

    results: list[dict[str, Any]] = []
    last_image: dict[str, Any] | None = None
    token = _ACTION_BATCH_CONFIRMED.set(confirmed_batch)
    try:
        for index, (name, args) in enumerate(prepared):
            fn = TOOL_FUNCTIONS[name]
            allowed_params = {p.name for p in inspect.signature(fn).parameters.values()}
            kwargs = {k: v for k, v in args.items() if k in allowed_params}
            raw = fn(**kwargs)
            step_payload = _payload_from_result(raw)
            if step_payload is None:
                step_payload = {"ok": False, "error": "invalid_step_output", "message": str(raw)[:300]}
            if isinstance(raw, list):
                for block in raw:
                    if isinstance(block, dict) and block.get("type") == "image":
                        last_image = block
            results.append({"step": index, "tool": name, **step_payload})
            if not step_payload.get("ok") or step_payload.get("status") in ("dispatched_unverified", "confirmation_required"):
                out: dict[str, Any] = {
                    "ok": False,
                    "error": "batch_stopped",
                    "error_code": step_payload.get("error_code") or step_payload.get("error") or "batch_stopped",
                    "message": f"第 {index + 1} 步 ({name}) 未成功，已中止后续动作。",
                    "failed_step": index,
                    "results": results,
                }
                if step_payload.get("status") == "confirmation_required":
                    out["status"] = "confirmation_required"
                    out["confirm_token"] = step_payload.get("confirm_token")
                return _dump(out)
    finally:
        _ACTION_BATCH_CONFIRMED.reset(token)

    summary = {"ok": True, "completed_steps": len(results), "results": results}
    if last_image is not None:
        return [{"type": "text", "text": _dump(summary)}, last_image]
    return _dump(summary)


def get_focused_text(hwnd: int | None = None, max_chars: int = 10000) -> str:
    if _as_int(max_chars) is None or not 1 <= max_chars <= 100000:
        return _error("invalid_arguments", "max_chars 必须为 1~100000。")
    target = winapi.foreground_info()
    if target is None or (hwnd is not None and (_as_int(hwnd) is None or hwnd != target["hwnd"])):
        return _error("target_changed", "目标窗口不在前台。")
    reason = security.forbidden_reason(target)
    if reason:
        return _error("forbidden_window", reason)
    try:
        result = focused_text.read(target["hwnd"], max_chars)
        if result.get("ok"):
            result["length"] = len(result["text"])
        return _dump(result)
    except Exception as exc:
        return _error("focused_text_unavailable", str(exc))


def type_text(
    text: str,
    method: str = "paste",
    confirm_token: str | None = None,
    hwnd: int | None = None,
    allow_unverified: bool = False,
) -> str:
    if not isinstance(text, str) or text == "":
        return _error("invalid_text", "text 必须是非空字符串。")
    if len(text) > 100000:
        return _error("invalid_text", "text 不能超过 100000 个字符。")
    if method not in ("paste", "unicode"):
        return _error("invalid_method", "method 必须是 paste 或 unicode。")
    if not isinstance(allow_unverified, bool):
        return _error("invalid_arguments", "allow_unverified 必须是布尔值。")
    params = {"text": text, "method": method, "hwnd": hwnd, "allow_unverified": allow_unverified}
    LOG.write("type_text", "start", {"text": text[:2000], "chars": len(text), "method": method})
    target = winapi.foreground_info()
    if target is None:
        return _error("no_foreground", "当前没有前台窗口，无法输入。")
    if hwnd is not None and (_as_int(hwnd) is None or hwnd != target["hwnd"]):
        return _error("target_changed", "指定窗口不是前台窗口；请先聚焦目标。")
    reason = security.forbidden_reason(target)
    if reason:
        return _error("forbidden_window", reason)
    try:
        before = focused_text.read(target["hwnd"])
    except Exception as exc:
        return _error("focused_text_unavailable", str(exc))
    if before.get("error") in ("password_control", "target_changed"):
        return _error(before["error"], "目标不允许输入。")
    if not before.get("focus_id"):
        return _error("focus_unavailable", "无法绑定焦点控件，输入未执行。")
    if not allow_unverified and (not before.get("ok") or not before.get("editable") or before.get("truncated")):
        return _error("focused_text_unavailable", "无法可靠读取可编辑控件，输入未执行。")
    params["focus_id"] = before["focus_id"]
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
        current_focus = focused_text.read(target["hwnd"])
        if current_focus.get("error") in ("password_control", "target_changed") or current_focus.get("focus_id") != before["focus_id"]:
            return _error("target_changed", "派发前焦点控件已变化。")
        if method == "unicode":
            result = winapi.type_text(text, expected_hwnd=int(target["hwnd"]))
            payload = {"ok": True, **result, "method": "unicode", "clipboard_restored": None, "target": target}
        else:
            pasted = paste_text(text, expected_hwnd=int(target["hwnd"]), expected_focus=before["focus_id"])
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
    verified, verification_error = focused_text.verify_insertion(target["hwnd"], before, text)
    payload.update(dispatched=True, verified=verified, verification_error=verification_error)
    if not verified:
        payload["paste_ok"] = False
        if not allow_unverified or verification_error == "target_changed":
            return _error("paste_unverified" if method == "paste" else "input_unverified",
                          "输入已派发但尚未验证；可调用 get_focused_text 确认，勿重复输入。",
                          dispatched=True, verified=False, paste_ok=False, verification_error=verification_error,
                          details={**payload, "ok": False})
        payload["status"] = "dispatched_unverified"
        payload["message"] = "按显式授权完成派发，文本落地未验证；请回读确认，勿重复输入。"
    else:
        payload["status"] = "verified"
    LOG.write(
        "type_text", "end", {"chars": len(text), "method": method}, target,
        outcome=f"{payload['characters']} chars",
    )
    return _dump(payload)


def press_keys(
    keys: str,
    confirm_token: str | None = None,
    hwnd: int | None = None,
    after_screenshot: bool = False,
    after_wait_ms: int = 150,
    screenshot_max_width: int = 1280,
    screenshot_format: str = "jpeg",
) -> str | list[dict[str, Any]]:
    if not isinstance(keys, str) or not keys.strip():
        return _error("invalid_keys", "keys 必须是非空字符串。")
    params = {"keys": keys.strip(), "hwnd": hwnd}
    LOG.write("press_keys", "start", params)
    target = winapi.foreground_info()
    if target is None:
        return _error("no_foreground", "当前没有前台窗口，无法按键。")
    if hwnd is not None and (_as_int(hwnd) is None or hwnd != target["hwnd"]):
        return _error("target_changed", "指定窗口不是前台窗口；请先聚焦目标。")
    try:
        params["focus_hwnd"] = winapi.focused_hwnd()
    except Exception as exc:
        return _error("focus_unavailable", str(exc))
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
        if winapi.focused_hwnd() != params["focus_hwnd"]:
            return _error("target_changed", "派发前焦点控件已变化。")
        result = winapi.press_keys(keys, expected_hwnd=int(target["hwnd"]))
    except ValueError as exc:
        LOG.write("press_keys", "blocked", params, target, outcome="target_changed")
        return _error("target_changed", str(exc), window=target)
    except Exception as exc:  # noqa: BLE001
        LOG.write("press_keys", "error", params, target, error=repr(exc))
        return _error("press_keys_failed", f"按键失败：{exc}")
    LOG.write("press_keys", "end", params, target, outcome=result["keys"])
    payload = {"ok": True, **result, "target": target}
    if after_screenshot:
        return _attach_after_screenshot(payload, hwnd, after_wait_ms, screenshot_max_width, screenshot_format)
    return _dump(payload)


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
    image.save(buffer, format="PNG", compress_level=1)
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


def inspect_ui(
    hwnd: int | None = None,
    query: str | None = None,
    interactive_only: bool = False,
    include_text: bool = True,
    include_elements: bool = False,
    max_elements: int = 150,
    max_depth: int = 12,
    timeout_ms: int = 2500,
    region: dict[str, Any] | None = None,
    include_visible_text: bool = False,
) -> str:
    """用 Windows UI Automation 控件树免截图读取窗口内所有可见控件、状态（含 DISABLED/selected）与屏幕物理像素中心坐标。"""
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    limit = _as_int(max_elements)
    if limit is None or not 1 <= limit <= 500:
        return _error("invalid_max_elements", "max_elements 必须在 1~500 之间。")
    depth = _as_int(max_depth)
    if depth is None or not 1 <= depth <= 30:
        return _error("invalid_max_depth", "max_depth 必须在 1~30 之间。")
    budget = _as_int(timeout_ms)
    if budget is None or not 200 <= budget <= 8000:
        return _error("invalid_timeout_ms", "timeout_ms 必须在 200~8000 之间。")
    if query is not None and not isinstance(query, str):
        return _error("invalid_query", "query 必须是字符串。")
    parsed_region: dict[str, int] | None = None
    if region is not None:
        if not isinstance(region, dict):
            return _error("invalid_region", "region 必须是 {x,y,width,height} 对象。")
        raw_region = {key: _as_int(region.get(key)) for key in ("x", "y", "width", "height")}
        if any(value is None for value in raw_region.values()):
            return _error("invalid_region", "region 需要整数 x、y、width、height。")
        parsed_region = {key: int(value) for key, value in raw_region.items() if value is not None}

    params = {
        "hwnd": hwnd, "query": query, "interactive_only": bool(interactive_only),
        "include_text": bool(include_text), "max_elements": limit,
        "include_visible_text": include_visible_text, "include_elements": include_elements,
        "max_depth": depth, "timeout_ms": budget, "region": parsed_region,
    }
    LOG.write("inspect_ui", "start", params)

    target = winapi.window_info(hwnd) if hwnd is not None else winapi.foreground_info()
    if target is None:
        return _error("invalid_hwnd" if hwnd is not None else "no_foreground", "目标窗口不存在或当前无前台窗口。")
    reason = security.forbidden_reason(target)
    if reason:
        LOG.write("inspect_ui", "blocked", params, target)
        return _error("forbidden_window", reason, window=target)

    try:
        result = ui_tree.inspect(
            hwnd=int(target["hwnd"]),
            max_elements=limit,
            max_depth=depth,
            interactive_only=bool(interactive_only),
            include_text=bool(include_text),
            skip_offscreen=True,
            query=query,
            timeout_ms=budget,
            region=parsed_region,
            include_hierarchy=include_elements,
            include_visible_text=include_visible_text,
        )
    except Exception as exc:  # noqa: BLE001
        LOG.write("inspect_ui", "error", params, target, error=repr(exc))
        return _error("uia_failed", f"UI 控件树读取失败：{exc}")

    if not result.get("ok"):
        LOG.write("inspect_ui", "error", params, target, error=str(result.get("error")))
        return _error(str(result.get("error") or "uia_failed"), str(result.get("message") or "UI 控件树读取失败。"))

    result["window"] = target
    if not include_elements:
        result.pop("elements", None)
    LOG.write(
        "inspect_ui", "end", params, target,
        outcome=f"{result.get('count', 0)} elements in {result.get('elapsed_ms', 0)}ms",
    )
    return _dump(result)


def read_screen_text(
    hwnd: int | None = None,
    region: dict[str, Any] | None = None,
    lang: str = "chi_sim+eng",
    max_items: int = 150,
    include_items: bool = False,
    capture_mode: str = "screen",
) -> str:
    """免截图整窗 OCR 读屏：一次返回窗口/区域内全部文字与屏幕物理像素中心点坐标，无需落盘看图。"""
    if not isinstance(lang, str) or not lang.strip():
        return _error("invalid_lang", "lang 必须是非空字符串。")
    limit = _as_int(max_items)
    if limit is None or not 1 <= limit <= 500:
        return _error("invalid_max_items", "max_items 必须在 1~500 之间。")
    if hwnd is not None:
        parsed = _as_int(hwnd)
        if parsed is None:
            return _error("invalid_hwnd", "hwnd 必须是整数。")
        hwnd = parsed
    if capture_mode not in ("screen", "wgc"):
        return _error("invalid_arguments", "capture_mode 必须为 screen 或 wgc。")
    if capture_mode == "wgc" and hwnd is None:
        return _error("invalid_hwnd", "WGC 需要指定目标窗口 hwnd。")
    params = {"hwnd": hwnd, "region": region, "lang": lang, "max_items": limit, "capture_mode": capture_mode}
    LOG.write("read_screen_text", "start", params)

    if hwnd is not None:
        info = winapi.window_info(hwnd)
        if info is None:
            return _error("invalid_hwnd", "窗口句柄无效或窗口已关闭。")
        reason = security.forbidden_reason(info)
        if reason:
            LOG.write("read_screen_text", "blocked", params, info)
            return _error("forbidden_window", reason, window=info)
        if capture_mode == "wgc" and info["minimized"]:
            return _error("window_minimized", "WGC 读屏需要已还原的窗口。")

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
            LOG.write("read_screen_text", "blocked", params, None)
            return _error(
                "forbidden_window",
                "读屏区域与受保护窗口相交，已拒绝；请先关闭或移动受保护窗口。",
                windows=forbidden_hits,
            )
        if capture_mode == "wgc":
            client = winapi.client_metrics(hwnd) if region is not None else capture_rect
            if any(capture_rect[n] <= 0 for n in ("width", "height")) or not all(
                client[pos] <= capture_rect[pos]
                and capture_rect[pos] + capture_rect[length] <= client[pos] + client[length]
                for pos, length in (("x", "width"), ("y", "height"))
            ):
                return _error("invalid_region", "WGC 的 region 必须完整位于目标窗口客户区内。")
            png = ocr.capture_window_png(hwnd, info["rect"], capture_rect)
            current = winapi.window_info(hwnd)
            if (not current or current["pid"] != info["pid"] or current["minimized"]
                    or current["rect"] != info["rect"] or winapi.client_metrics(hwnd) != client):
                return _error("target_changed", "取帧时目标窗口或客户区发生变化，请重新读屏。")
            reason = security.forbidden_reason(current)
            if reason:
                return _error("forbidden_window", reason, window=current)
            metadata = {"mode": "region" if region is not None else "window", "hwnd": hwnd,
                        "width": capture_rect["width"], "height": capture_rect["height"],
                        "origin": {"x": capture_rect["x"], "y": capture_rect["y"]}}
        else:
            if region is not None:
                image, metadata = winapi.grab_image(region=parsed_region)
            else:
                image, metadata = winapi.grab_image(hwnd=hwnd)
            buffer = BytesIO()
            image.save(buffer, format="PNG", compress_level=1)
            png = buffer.getvalue()
    except ValueError as exc:
        return _error("invalid_region", str(exc))
    except Exception as exc:  # noqa: BLE001
        if capture_mode == "wgc":
            LOG.write("read_screen_text", "error", params, error=repr(exc))
            return _error("wgc_capture_failed", f"WGC 窗口取帧失败：{exc}")
        return _error("screenshot_failed", f"读屏截图失败：{exc}")

    recognized = ocr.recognize(png, lang)
    if not recognized.get("ok"):
        LOG.write("read_screen_text", "error", params, error=recognized.get("error"))
        code = recognized.get("error") or "ocr_unavailable"
        extra = {"install_hint": recognized.get("install_hint")} if code == "ocr_unavailable" else {}
        return _error(code, recognized.get("message") or "OCR 引擎不可用。", **extra)

    blocks = ocr.extract_text_blocks(recognized.get("lines") or [], max_items=limit)
    origin = metadata["origin"]
    scale = float(metadata.get("scale") or 1.0)
    items: list[dict[str, Any]] = []
    compact_lines: list[str] = []
    for block in blocks:
        rect = block["rect"]
        cx = int(round(origin["x"] + block["cx"] / scale))
        cy = int(round(origin["y"] + block["cy"] / scale))
        screen_rect = {
            "x": int(round(origin["x"] + rect["x"] / scale)),
            "y": int(round(origin["y"] + rect["y"] / scale)),
            "width": int(round(rect["width"] / scale)),
            "height": int(round(rect["height"] / scale)),
        }
        items.append({"text": block["text"], "cx": cx, "cy": cy, "rect": screen_rect})
        compact_lines.append(f"\"{block['text']}\" ({cx},{cy})")

    LOG.write("read_screen_text", "end", params, outcome=f"{len(items)} blocks")
    payload: dict[str, Any] = {
        "ok": True,
        "count": len(items),
        "compact": "\n".join(compact_lines),
        "engine": recognized.get("engine"),
        "ocr_lang": recognized.get("lang"),
        "coordinate_space": "screen-physical-pixels",
        "image": {
            "mode": metadata["mode"],
            "capture_method": capture_mode,
            "hwnd": metadata.get("hwnd"),
            "width": metadata["width"],
            "height": metadata["height"],
        },
    }
    if include_items:
        payload["items"] = items
    return _dump(payload)


def chrome_cdp(
    action: str,
    target_id: str | None = None,
    url_contains: str | None = None,
    title_contains: str | None = None,
    url: str | None = None,
    new_tab: bool = True,
    ref: int | None = None,
    selector: str | None = None,
    text: str | None = None,
    index: int = 0,
    value: str | None = None,
    submit: bool = False,
    key: str | None = None,
    query: str | None = None,
    interactive_only: bool = False,
    include_text: bool = True,
    include_elements: bool = False,
    max_elements: int = 150,
    max_chars: int = 8000,
    wait_ms: int = 450,
    after_inspect: bool = True,
    browser: str = "auto",
    port: int | None = None,
    confirm_token: str | None = None,
) -> str:
    """免截图、免抢鼠标直连本地已登录 Chrome/Edge（通过 DevToolsActivePort CDP）。"""
    all_actions = _CDP_READ_ACTIONS | _CDP_WRITE_ACTIONS
    if not isinstance(action, str) or action.strip() not in all_actions:
        return _error("invalid_action", f"action 必须是：{', '.join(sorted(all_actions))}。")
    action = action.strip()
    if browser not in ("auto", "chrome", "edge"):
        return _error("invalid_browser", "browser 必须是 auto、chrome 或 edge。")
    if ref is not None:
        parsed_ref = _as_int(ref)
        if parsed_ref is None or parsed_ref < 1:
            return _error("invalid_ref", "ref 必须是正整数。")
        ref = parsed_ref
    idx = _as_int(index)
    if idx is None or not 0 <= idx <= 100:
        return _error("invalid_index", "index 必须是 0~100 的整数。")
    limit = _as_int(max_elements)
    if limit is None or not 1 <= limit <= 500:
        return _error("invalid_max_elements", "max_elements 必须在 1~500 之间。")
    chars_limit = _as_int(max_chars)
    if chars_limit is None or not 100 <= chars_limit <= 100000:
        return _error("invalid_max_chars", "max_chars 必须在 100~100000 之间。")
    wait_val = _as_int(wait_ms)
    if wait_val is None or not 0 <= wait_val <= 15000:
        return _error("invalid_wait_ms", "wait_ms 必须在 0~15000 之间。")
    if port is not None:
        parsed_port = _as_int(port)
        if parsed_port is None or not 1 <= parsed_port <= 65535:
            return _error("invalid_port", "port 必须是 1~65535 的整数。")
        port = parsed_port

    if action == "open_url":
        if not isinstance(url, str) or not url.strip():
            return _error("invalid_url", "open_url 需要非空 url。")
        reason = cdp.forbidden_page_reason(url, "")
        if reason:
            return _error("forbidden_page", reason)
    elif action in ("click", "fill") and ref is None and not selector and not text:
        return _error("invalid_target_locator", f"{action} 需要提供 ref、selector 或 text 至少一个定位条件。")
    if action == "fill" and not isinstance(value, str):
        return _error("invalid_value", "fill 需要提供字符串 value。")
    if action == "press_key" and (not isinstance(key, str) or not key.strip()):
        return _error("invalid_key", "press_key 需要非空 key。")

    params = {
        "action": action, "target_id": target_id, "url_contains": url_contains,
        "title_contains": title_contains, "url": url, "new_tab": bool(new_tab),
        "ref": ref, "selector": selector, "text": text, "index": idx,
        "value": value[:200] if isinstance(value, str) else None,
        "submit": bool(submit), "key": key, "browser": browser, "port": port,
    }
    LOG.write("chrome_cdp", "start", params)

    if action in _CDP_WRITE_ACTIONS:
        proc_name = "msedge.exe" if browser == "edge" else "chrome.exe"
        gate_target = {"hwnd": 0, "process": proc_name, "title": title_contains or url or target_id or "Chrome CDP"}
        blocked = _gate(f"chrome_cdp.{action}", params, gate_target, confirm_token)
        if blocked:
            LOG.write("chrome_cdp", "pending_confirmation", params, gate_target)
            return blocked

    try:
        result = cdp.execute(
            action,
            target_id=target_id,
            url_contains=url_contains,
            title_contains=title_contains,
            url=url,
            new_tab=bool(new_tab),
            ref=ref,
            selector=selector,
            text=text,
            index=idx,
            value=value,
            submit=bool(submit),
            key=key,
            query=query,
            interactive_only=bool(interactive_only),
            include_text=bool(include_text),
            include_elements=bool(include_elements),
            max_elements=limit,
            max_chars=chars_limit,
            wait_ms=wait_val,
            after_inspect=bool(after_inspect),
            browser=browser,
            port=port,
        )
    except cdp.CdpError as exc:
        LOG.write("chrome_cdp", "error", params, error=f"{exc.code}: {exc}")
        return _error(exc.code, str(exc), **exc.extra)
    except Exception as exc:  # noqa: BLE001
        LOG.write("chrome_cdp", "error", params, error=repr(exc))
        return _error("cdp_failed", f"CDP 执行异常：{exc}")

    LOG.write("chrome_cdp", "end", params, outcome=action)
    return _dump(result)


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
        "format": {"type": "string", "enum": ["png", "jpeg"], "default": "png", "description": "图像格式：png（无损）或 jpeg（更快、体积更小）。"},
        "quality": {"type": "integer", "default": 82, "minimum": 40, "maximum": 95, "description": "jpeg 压缩质量（40~95），默认 82。"},
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
        "after_screenshot": {"type": "boolean", "default": False, "description": "点击成功后等待 after_wait_ms 并附带返回最新截图，省去额外一轮请求。"},
        "after_wait_ms": {"type": "integer", "default": 150, "minimum": 0, "maximum": 5000},
        "screenshot_max_width": {"type": "integer", "default": 1280, "minimum": 0, "maximum": 4096},
        "screenshot_format": {"type": "string", "enum": ["png", "jpeg"], "default": "jpeg"},
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
        "allow_unverified": {"type": "boolean", "default": False, "description": "显式允许无法回读时派发；仍核对目标与焦点，返回 verified=false，不代表文本已落地。"},
        "hwnd": {"type": ["integer", "null"], "default": None},
        "text": {"type": "string", "maxLength": 100000, "description": "要输入的文本，支持中文、换行与制表符。"},
        "method": {"type": "string", "enum": ["paste", "unicode"], "default": "paste", "description": "paste 使用剪贴板并恢复；unicode 使用 SendInput。"},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["text"],
}
_KEYS_SCHEMA = {
    "type": "object",
    "properties": {
        "hwnd": {"type": ["integer", "null"], "default": None},
        "keys": {"type": "string", "description": "组合键，例如 ctrl+a、ctrl+c、alt+tab、win+d、f5。"},
        "confirm_token": {"type": ["string", "null"], "default": None},
        "after_screenshot": {"type": "boolean", "default": False, "description": "按键成功后等待 after_wait_ms 并附带返回最新截图。"},
        "after_wait_ms": {"type": "integer", "default": 150, "minimum": 0, "maximum": 5000},
        "screenshot_max_width": {"type": "integer", "default": 1280, "minimum": 0, "maximum": 4096},
        "screenshot_format": {"type": "string", "enum": ["png", "jpeg"], "default": "jpeg"},
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
_INSPECT_UI_SCHEMA = {
    "type": "object",
    "properties": {
        "hwnd": {"type": ["integer", "null"], "default": None, "description": "目标窗口句柄；省略则检查当前前台窗口。"},
        "query": {"type": ["string", "null"], "default": None, "maxLength": 200, "description": "按名称或值过滤。开启 include_visible_text 后，文本控件按可见原文匹配，仅支持 ValuePattern 的控件仍按当前值匹配。"},
        "interactive_only": {"type": "boolean", "default": False, "description": "为 true 时仅返回按钮/菜单/输入框/单选框等可交互控件。"},
        "include_text": {"type": "boolean", "default": True, "description": "是否包含普通文本节点（便于直接读数字和提示信息）。"},
        "include_elements": {"type": "boolean", "default": False, "description": "附带 elements 及 hierarchy。按本次结果的 parent_id 回溯命中控件的祖先。"},
        "include_visible_text": {"type": "boolean", "default": False, "description": "用 UIA TextPattern 读取控件可见原文，每个控件至多 2048 个 UTF-16 代码单元。"},
        "max_elements": {"type": "integer", "default": 150, "minimum": 1, "maximum": 500},
        "max_depth": {"type": "integer", "default": 12, "minimum": 1, "maximum": 30},
        "timeout_ms": {"type": "integer", "default": 2500, "minimum": 200, "maximum": 8000},
        "region": {
            "type": ["object", "null"],
            "default": None,
            "description": "可选屏幕物理像素过滤区域。",
            "properties": {
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "width": {"type": "integer"}, "height": {"type": "integer"},
            },
            "required": ["x", "y", "width", "height"],
        },
    },
}
_READ_SCREEN_TEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "capture_mode": {"type": "string", "enum": ["screen", "wgc"], "default": "screen",
                         "description": "screen 读取桌面可见像素；wgc 仅捕获指定 hwnd 的客户区，可读取被其他窗口遮挡的内容。"},
        "hwnd": {"type": ["integer", "null"], "default": None, "description": "窗口句柄；省略则读整屏。"},
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
        "max_items": {"type": "integer", "default": 150, "minimum": 1, "maximum": 500},
        "include_items": {"type": "boolean", "default": False, "description": "默认只返回精简 compact 清单以防输出落盘；设为 true 时附带完整 items 数组。"},
    },
}
_CHROME_CDP_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["list_tabs", "inspect_page", "read_text", "open_url", "activate_tab", "close_tab", "click", "fill", "press_key"],
            "description": "CDP 动作：list_tabs/inspect_page/read_text 只读免确认；open_url/activate_tab/close_tab/click/fill/press_key 走确认门，且后台执行不抢物理鼠标。",
        },
        "target_id": {"type": ["string", "null"], "default": None, "description": "目标标签页 target_id（由 list_tabs 或 open_url 返回）。"},
        "url_contains": {"type": ["string", "null"], "default": None, "description": "未传 target_id 时按 URL 子串匹配标签页。"},
        "title_contains": {"type": ["string", "null"], "default": None, "description": "未传 target_id 时按标题子串匹配标签页。"},
        "url": {"type": ["string", "null"], "default": None, "maxLength": 8192, "description": "open_url 必填的目标 URL。"},
        "new_tab": {"type": "boolean", "default": True, "description": "open_url 是否新开标签页；false 则在匹配页签直接导航。"},
        "ref": {"type": ["integer", "null"], "default": None, "minimum": 1, "description": "click/fill 首选：inspect_page 输出的 [ref] 编号。"},
        "selector": {"type": ["string", "null"], "default": None, "maxLength": 1000, "description": "click/fill 可选 CSS 选择器（自动穿透 Shadow DOM）。"},
        "text": {"type": ["string", "null"], "default": None, "maxLength": 500, "description": "click/fill 可选可见文本或 aria-label 匹配（自动穿透 Shadow DOM）。"},
        "index": {"type": "integer", "default": 0, "minimum": 0, "maximum": 100, "description": "text 匹配到多项时取第几个（默认 0）。"},
        "value": {"type": ["string", "null"], "default": None, "maxLength": 100000, "description": "fill 必填的输入文本。"},
        "submit": {"type": "boolean", "default": False, "description": "fill 后是否自动发送 Enter。"},
        "key": {"type": ["string", "null"], "default": None, "maxLength": 50, "description": "press_key 必填按键名，如 Enter、Escape、Tab、ArrowDown。"},
        "query": {"type": ["string", "null"], "default": None, "maxLength": 200, "description": "inspect_page 可选关键字过滤。"},
        "interactive_only": {"type": "boolean", "default": False},
        "include_text": {"type": "boolean", "default": True},
        "include_elements": {"type": "boolean", "default": False},
        "max_elements": {"type": "integer", "default": 150, "minimum": 1, "maximum": 500},
        "max_chars": {"type": "integer", "default": 8000, "minimum": 100, "maximum": 100000},
        "wait_ms": {"type": "integer", "default": 450, "minimum": 0, "maximum": 15000, "description": "open_url/click 后等待渲染的毫秒数。"},
        "after_inspect": {"type": "boolean", "default": True, "description": "open_url/click 后是否顺带返回最新 inspect_page 清单，省去额外一轮请求。"},
        "browser": {"type": "string", "enum": ["auto", "chrome", "edge"], "default": "auto"},
        "port": {"type": ["integer", "null"], "default": None, "minimum": 1, "maximum": 65535},
        "confirm_token": {"type": ["string", "null"], "default": None},
    },
    "required": ["action"],
}

TOOLS = [
    {"name": "action_batch", "description": "一次调用按顺序执行多步桌面连招（支持 focus_window/click/hover/scroll/wait/type_text/press_keys/find_text/inspect_ui/read_screen_text/chrome_cdp/screenshot），任一步失败即停；优先用 chrome_cdp（浏览器网页）或 inspect_ui（桌面应用）免截图操作。",
     "inputSchema": {"type": "object", "properties": {
       "actions": {"type": "array", "minItems": 1, "maxItems": 20,
       "items": {"type": "object", "properties": {"tool": {"type": "string", "enum": ["focus_window", "click", "hover", "scroll", "wait", "type_text", "press_keys", "find_text", "inspect_ui", "read_screen_text", "chrome_cdp", "screenshot"]}, "arguments": {"type": "object", "additionalProperties": True}}, "required": ["tool", "arguments"]}},
       "confirm_token": {"type": ["string", "null"], "default": None}}, "required": ["actions"]}},
    {"name": "input_batch", "description": "一次确认执行同一前台窗口的有序输入/按键批次；失败即停止。",
     "inputSchema": {"type": "object", "properties": {
       "hwnd": {"type": "integer"}, "actions": {"type": "array", "minItems": 1, "maxItems": 20,
       "items": {"type": "object", "properties": {"tool": {"type": "string", "enum": ["type_text", "press_keys"]}, "arguments": {"type": "object", "additionalProperties": True}}, "required": ["tool", "arguments"]}},
       "confirm_token": {"type": ["string", "null"], "default": None}}, "required": ["hwnd", "actions"]}},
    {"name": "get_focused_text", "description": "只读当前焦点控件文本；不支持或密码控件明确失败，不改变焦点。",
     "inputSchema": {"type": "object", "properties": {
         "hwnd": {"type": ["integer", "null"], "default": None},
         "max_chars": {"type": "integer", "minimum": 1, "maximum": 100000, "default": 10000}}}},
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
    {
        "name": "inspect_ui",
        "description": "读取 UIA 控件名称、状态和屏幕物理像素中心点。用 include_elements 查看控件所属行或分组，用 include_visible_text 读取支持 TextPattern 的控件可见原文。只读。",
        "inputSchema": _INSPECT_UI_SCHEMA,
    },
    {
        "name": "read_screen_text",
        "description": "OCR 读取窗口或区域内的文字及屏幕物理像素中心点。默认读取桌面可见像素；需读取被遮挡的窗口时指定 hwnd 和 capture_mode=wgc。只读。",
        "inputSchema": _READ_SCREEN_TEXT_SCHEMA,
    },
    {
        "name": "chrome_cdp",
        "description": "免截图、免抢鼠标直连本地已登录 Chrome/Edge（通过 DevToolsActivePort CDP WebSocket）：毫秒级列出标签页、穿透 Shadow DOM 读取网页真实控件与 [DISABLED]/[selected] 状态、后台直接点击/填表/打开链接。需要 Chrome 开启 chrome://inspect/#remote-debugging。",
        "inputSchema": _CHROME_CDP_SCHEMA,
    },
]

TOOL_FUNCTIONS = {
    "action_batch": action_batch,
    "list_windows": list_windows,
    "focus_window": focus_window,
    "screenshot": screenshot,
    "click": click,
    "scroll": scroll,
    "input_batch": input_batch,
    "get_focused_text": get_focused_text,
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
    "inspect_ui": inspect_ui,
    "read_screen_text": read_screen_text,
    "chrome_cdp": chrome_cdp,
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
        cdp.close()
        ocr.close()
        ui_tree.close()
        focused_text.close()
        LOG.close()


if __name__ == "__main__":
    sys.exit(main())
