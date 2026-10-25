#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 桌面访问基础层：DPI、窗口枚举、前台切换、截图。

设计约束：
1. 进程启动时切到 Per-Monitor V2 DPI 感知，之后所有坐标都是物理像素。
2. 只用 ctypes 调用 user32 / kernel32 / dwmapi，不依赖 pywin32。
3. 截图统一用 Pillow ImageGrab：整屏取虚拟屏幕，窗口取客户区。
4. 本模块只做只读与窗口焦点操作；输入注入在后续轮次加入。
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes as w
from dataclasses import dataclass
from io import BytesIO
from typing import Any

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
shcore = ctypes.WinDLL("shcore", use_last_error=True)

# ---------------------------------------------------------------- DPI

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
PROCESS_PER_MONITOR_DPI_AWARE = 2


def enable_dpi_awareness() -> str:
    """把当前进程切到 Per-Monitor V2；返回实际生效的模式，便于日志。"""
    try:
        if user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    try:
        if shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE) == 0:
            return "per-monitor"
    except (AttributeError, OSError):
        pass
    try:
        if user32.SetProcessDPIAware():
            return "system"
    except (AttributeError, OSError):
        pass
    return "unaware"


# ---------------------------------------------------------------- Win32 基础类型

class RECT(ctypes.Structure):
    _fields_ = [("left", w.LONG), ("top", w.LONG), ("right", w.LONG), ("bottom", w.LONG)]


class POINT(ctypes.Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG)]


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", w.UINT),
        ("flags", w.UINT),
        ("showCmd", w.UINT),
        ("ptMinPosition", POINT),
        ("ptMaxPosition", POINT),
        ("rcNormalPosition", RECT),
    ]


WNDENUMPROC = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)

user32.GetForegroundWindow.restype = w.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [w.HWND]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.GetWindowRect.restype = w.BOOL
user32.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = w.BOOL
user32.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(RECT)]
user32.ClientToScreen.restype = w.BOOL
user32.ClientToScreen.argtypes = [w.HWND, ctypes.POINTER(POINT)]
user32.GetWindowThreadProcessId.restype = w.DWORD
user32.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
user32.IsWindowVisible.restype = w.BOOL
user32.IsWindowVisible.argtypes = [w.HWND]
user32.IsWindow.restype = w.BOOL
user32.IsWindow.argtypes = [w.HWND]
user32.IsIconic.restype = w.BOOL
user32.IsIconic.argtypes = [w.HWND]
user32.ShowWindow.restype = w.BOOL
user32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
user32.SetForegroundWindow.restype = w.BOOL
user32.SetForegroundWindow.argtypes = [w.HWND]
user32.BringWindowToTop.restype = w.BOOL
user32.BringWindowToTop.argtypes = [w.HWND]
user32.AttachThreadInput.restype = w.BOOL
user32.AttachThreadInput.argtypes = [w.DWORD, w.DWORD, w.BOOL]
user32.GetWindowLongPtrW.restype = ctypes.c_longlong
user32.GetWindowLongPtrW.argtypes = [w.HWND, ctypes.c_int]
user32.GetWindowPlacement.restype = w.BOOL
user32.GetWindowPlacement.argtypes = [w.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.WindowFromPoint.restype = w.HWND
user32.WindowFromPoint.argtypes = [POINT]
user32.GetAncestor.restype = w.HWND
user32.GetAncestor.argtypes = [w.HWND, w.UINT]
user32.GetCursorPos.restype = w.BOOL
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]

kernel32.GetCurrentThreadId.restype = w.DWORD
kernel32.OpenProcess.restype = w.HANDLE
kernel32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
kernel32.QueryFullProcessImageNameW.restype = w.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
kernel32.CloseHandle.restype = w.BOOL
kernel32.CloseHandle.argtypes = [w.HANDLE]

dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long
dwmapi.DwmGetWindowAttribute.argtypes = [w.HWND, w.DWORD, ctypes.c_void_p, w.DWORD]

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
GA_ROOT = 2
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SM_CXSCREEN = 0
SM_CYSCREEN = 1


def _hwnd(value: int) -> w.HWND:
    return w.HWND(int(value))


def _rect_to_dict(rect: RECT) -> dict[str, int]:
    return {
        "x": int(rect.left),
        "y": int(rect.top),
        "width": int(rect.right - rect.left),
        "height": int(rect.bottom - rect.top),
    }


def screen_metrics() -> dict[str, int]:
    """虚拟屏幕（所有显示器）与主屏的物理像素尺寸。"""
    return {
        "x": int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN)),
        "y": int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN)),
        "width": int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)),
        "height": int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)),
        "primary_width": int(user32.GetSystemMetrics(SM_CXSCREEN)),
        "primary_height": int(user32.GetSystemMetrics(SM_CYSCREEN)),
    }


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(_hwnd(hwnd))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(_hwnd(hwnd), buffer, length + 1)
    return buffer.value.strip()


def _window_class(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    if user32.GetClassNameW(_hwnd(hwnd), buffer, 256):
        return buffer.value
    return ""


def _process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = w.DWORD(len(buffer))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return os.path.basename(buffer.value)
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _dwm_rect(hwnd: int) -> RECT | None:
    rect = RECT()
    try:
        result = dwmapi.DwmGetWindowAttribute(
            _hwnd(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
        )
    except OSError:
        return None
    if result == 0 and rect.right > rect.left and rect.bottom > rect.top:
        return rect
    return None


def _is_cloaked(hwnd: int) -> bool:
    value = w.DWORD(0)
    try:
        result = dwmapi.DwmGetWindowAttribute(
            _hwnd(hwnd), DWMWA_CLOAKED, ctypes.byref(value), ctypes.sizeof(value)
        )
    except OSError:
        return False
    return result == 0 and value.value != 0


def _restore_rect(hwnd: int) -> dict[str, int] | None:
    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)
    if not user32.GetWindowPlacement(_hwnd(hwnd), ctypes.byref(placement)):
        return None
    return _rect_to_dict(placement.rcNormalPosition)


def window_info(hwnd: int) -> dict[str, Any] | None:
    """读取一个窗口的稳定快照；窗口无效时返回 None。"""
    hwnd = int(hwnd)
    if hwnd <= 0 or not user32.IsWindow(_hwnd(hwnd)):
        return None
    pid = w.DWORD(0)
    user32.GetWindowThreadProcessId(_hwnd(hwnd), ctypes.byref(pid))
    rect = _dwm_rect(hwnd)
    if rect is None:
        rect = RECT()
        user32.GetWindowRect(_hwnd(hwnd), ctypes.byref(rect))
    exstyle = user32.GetWindowLongPtrW(_hwnd(hwnd), GWL_EXSTYLE)
    info: dict[str, Any] = {
        "hwnd": hwnd,
        "process": _process_name(pid.value),
        "pid": int(pid.value),
        "title": _window_title(hwnd),
        "class": _window_class(hwnd),
        "rect": _rect_to_dict(rect),
        "minimized": bool(user32.IsIconic(_hwnd(hwnd))),
        "foreground": int(user32.GetForegroundWindow() or 0) == hwnd,
        "tool_window": bool(exstyle & WS_EX_TOOLWINDOW),
    }
    if info["minimized"]:
        restore = _restore_rect(hwnd)
        if restore:
            # 最小化时 GetWindowRect 返回屏幕外的图标占位矩形，
            # 对调用方有意义的是还原后的窗口矩形。
            info["iconic_rect"] = info["rect"]
            info["rect"] = restore
    return info


def list_windows(include_tool_windows: bool = False) -> list[dict[str, Any]]:
    """枚举可见的顶层窗口；跳过无标题、DWM 隐藏和零尺寸窗口。"""
    rows: list[dict[str, Any]] = []

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(_hwnd(hwnd)) or _is_cloaked(hwnd):
            return True
        if not _window_title(hwnd):
            return True
        info = window_info(hwnd)
        if info is None:
            return True
        if info["tool_window"] and not include_tool_windows:
            return True
        if info["rect"]["width"] <= 0 or info["rect"]["height"] <= 0:
            return True
        rows.append(info)
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    rows.sort(key=lambda item: (not item["foreground"], item["minimized"], item["process"].lower(), item["title"].lower()))
    return rows


def _normalize_process(value: str) -> str:
    name = os.path.basename(value.strip()).lower()
    return name[:-4] if name.endswith(".exe") else name


def find_windows(process: str | None = None, title: str | None = None) -> list[dict[str, Any]]:
    """按进程名（可省略 .exe）和标题关键字筛选可见窗口。"""
    wanted_process = _normalize_process(process) if process else None
    wanted_title = title.casefold() if title else None
    matches = []
    for info in list_windows():
        if wanted_process and _normalize_process(info["process"]) != wanted_process:
            continue
        if wanted_title and wanted_title not in info["title"].casefold():
            continue
        matches.append(info)
    return matches


def client_metrics(hwnd: int) -> dict[str, int]:
    """客户区在屏幕上的物理像素原点和尺寸。"""
    rect = RECT()
    if not user32.GetClientRect(_hwnd(hwnd), ctypes.byref(rect)):
        raise ctypes.WinError(ctypes.get_last_error())
    origin = POINT(0, 0)
    far = POINT(int(rect.right), int(rect.bottom))
    if not user32.ClientToScreen(_hwnd(hwnd), ctypes.byref(origin)):
        raise ctypes.WinError(ctypes.get_last_error())
    user32.ClientToScreen(_hwnd(hwnd), ctypes.byref(far))
    return {
        "x": int(origin.x),
        "y": int(origin.y),
        "width": int(far.x - origin.x),
        "height": int(far.y - origin.y),
    }


def focus_window(hwnd: int) -> dict[str, Any]:
    """还原最小化窗口并尝试切到前台；返回真实前台状态。"""
    info = window_info(hwnd)
    if info is None:
        raise ValueError("窗口句柄无效或窗口已关闭。")
    was_minimized = bool(info["minimized"])
    if was_minimized:
        user32.ShowWindow(_hwnd(hwnd), SW_RESTORE)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and user32.IsIconic(_hwnd(hwnd)):
            time.sleep(0.05)

    if int(user32.GetForegroundWindow() or 0) != int(hwnd):
        foreground = int(user32.GetForegroundWindow() or 0)
        current_thread = kernel32.GetCurrentThreadId()
        foreground_thread = (
            user32.GetWindowThreadProcessId(_hwnd(foreground), None) if foreground else 0
        )
        attached = False
        if foreground_thread and foreground_thread != current_thread:
            attached = bool(user32.AttachThreadInput(current_thread, foreground_thread, True))
        try:
            user32.BringWindowToTop(_hwnd(hwnd))
            user32.SetForegroundWindow(_hwnd(hwnd))
        finally:
            if attached:
                user32.AttachThreadInput(current_thread, foreground_thread, False)

        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if int(user32.GetForegroundWindow() or 0) == int(hwnd):
                break
            time.sleep(0.05)

    info = window_info(hwnd) or info
    info["was_minimized"] = was_minimized
    info["foreground"] = int(user32.GetForegroundWindow() or 0) == int(hwnd)
    return info


def window_at_point(x: int, y: int) -> dict[str, Any] | None:
    """屏幕上某一点所在的顶层窗口。"""
    child = user32.WindowFromPoint(POINT(int(x), int(y)))
    if not child:
        return None
    root = user32.GetAncestor(child, GA_ROOT) or child
    return window_info(int(root))


def capture(max_width: int = 1600, hwnd: int | None = None) -> tuple[bytes, dict[str, Any]]:
    """截图并编码为 PNG；返回 (png_bytes, metadata)。

    整屏截图覆盖所有显示器，origin 为虚拟屏幕左上角；窗口截图只含客户区，
    origin 为客户区左上角。metadata 的 width/height 是缩放后的像素尺寸，
    original_width/original_height 是截图原始物理像素尺寸。
    """
    from PIL import ImageGrab

    if max_width and (max_width < 320 or max_width > 4096):
        raise ValueError("max_width 必须是 0（不缩放）或 320~4096 之间的整数。")

    origin: dict[str, int]
    if hwnd is not None:
        hwnd = int(hwnd)
        info = window_info(hwnd)
        if info is None:
            raise ValueError("窗口句柄无效或窗口已关闭。")
        if info["minimized"]:
            raise ValueError("窗口已最小化，先调用 focus_window 还原后再截图。")
        client = client_metrics(hwnd)
        try:
            image = ImageGrab.grab(window=hwnd)
        except OSError as exc:
            raise ValueError(f"窗口截图失败：{exc}") from exc
        frame = info["rect"]
        if image.size != (client["width"], client["height"]):
            left = client["x"] - frame["x"]
            top = client["y"] - frame["y"]
            box = (left, top, left + client["width"], top + client["height"])
            if left >= 0 and top >= 0 and box[2] <= image.width and box[3] <= image.height:
                image = image.crop(box)
        origin = {"x": client["x"], "y": client["y"]}
        mode = "window"
    else:
        metrics = screen_metrics()
        image = ImageGrab.grab(all_screens=True)
        if image.size != (metrics["width"], metrics["height"]):
            raise ValueError(
                f"整屏截图尺寸 {image.size} 与系统虚拟屏幕 "
                f"{metrics['width']}x{metrics['height']} 不一致。"
            )
        origin = {"x": metrics["x"], "y": metrics["y"]}
        mode = "screen"

    original_width, original_height = image.size
    scale = 1.0
    if max_width and original_width > max_width:
        target_width = int(max_width)
        target_height = max(1, round(original_height * target_width / original_width))
        image = image.resize((target_width, target_height), resample=3)  # LANCZOS
        scale = target_width / original_width

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()

    metadata = {
        "mode": mode,
        "hwnd": int(hwnd) if hwnd is not None else None,
        "origin": origin,
        "width": int(image.width),
        "height": int(image.height),
        "original_width": int(original_width),
        "original_height": int(original_height),
        "scale": round(scale, 6),
        "png_bytes": len(data),
        "screen": screen_metrics(),
    }
    return data, metadata


def current_cursor() -> dict[str, int]:
    point = POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"x": int(point.x), "y": int(point.y)}
