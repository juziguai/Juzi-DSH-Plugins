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
import hashlib
import os
import time
from ctypes import wintypes as w
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


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", w.DWORD),
    ]


MONITORENUMPROC = ctypes.WINFUNCTYPE(w.BOOL, w.HMONITOR, w.HDC, ctypes.POINTER(RECT), w.LPARAM)


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
user32.GetWindow.restype = w.HWND
user32.GetWindow.argtypes = [w.HWND, w.UINT]
user32.IsZoomed.restype = w.BOOL
user32.IsZoomed.argtypes = [w.HWND]
user32.SetWindowPos.restype = w.BOOL
user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
user32.PostMessageW.restype = w.BOOL
user32.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
user32.EnumDisplayMonitors.restype = w.BOOL
user32.EnumDisplayMonitors.argtypes = [w.HDC, ctypes.POINTER(RECT), MONITORENUMPROC, w.LPARAM]
user32.GetMonitorInfoW.restype = w.BOOL
user32.GetMonitorInfoW.argtypes = [w.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.MonitorFromWindow.restype = w.HMONITOR
user32.MonitorFromWindow.argtypes = [w.HWND, w.DWORD]

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
GW_OWNER = 4
SW_RESTORE = 9
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_SHOWNORMAL = 1
WM_CLOSE = 0x0010
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
MONITOR_DEFAULTTOPRIMARY = 1
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


def rects_intersect(first: dict[str, int], second: dict[str, int]) -> bool:
    return not (
        first["x"] + first["width"] <= second["x"]
        or second["x"] + second["width"] <= first["x"]
        or first["y"] + first["height"] <= second["y"]
        or second["y"] + second["height"] <= first["y"]
    )


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
        "maximized": bool(user32.IsZoomed(_hwnd(hwnd))),
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


def dialog_windows(pid: int, owner_hwnd: int | None = None) -> list[dict[str, Any]]:
    """枚举指定进程的可见 #32770 对话框；owner_hwnd 非零时只保留其 owned 对话框。"""
    rows = []
    for item in list_windows(include_tool_windows=True):
        if int(item["pid"]) != int(pid) or item["class"] != "#32770":
            continue
        if owner_hwnd is not None:
            owner = user32.GetWindow(_hwnd(item["hwnd"]), GW_OWNER)
            owner_value = int(owner or 0)
            if owner_value not in (0, int(owner_hwnd)):
                continue
        rows.append(item)
    return rows


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


def actual_target_at(x: int, y: int, expected_hwnd: int | None = None) -> dict[str, Any] | None:
    """取屏幕落点的真实顶层窗口；expected_hwnd 非空时必须一致，否则抛 target_changed。"""
    info = window_at_point(int(x), int(y))
    if expected_hwnd is not None:
        if info is None or int(info["hwnd"]) != int(expected_hwnd):
            actual = None if info is None else f"{info['hwnd']}/{info.get('process')}/{info.get('title')}"
            raise ValueError(
                f"target_changed：落点实际窗口已变为 {actual}，与预期 hwnd {expected_hwnd} 不一致，已中止。"
            )
    return info


# ---------------------------------------------------------------- 显示器与窗口布局

def monitors() -> list[dict[str, Any]]:
    """枚举显示器，返回物理像素的整屏矩形与工作区（排除任务栏）。"""
    rows: list[dict[str, Any]] = []

    def callback(hmonitor, _hdc, _rect, _lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            rows.append(
                {
                    "monitor": _rect_to_dict(info.rcMonitor),
                    "work_area": _rect_to_dict(info.rcWork),
                    "primary": bool(info.dwFlags & 1),
                }
            )
        return True

    if not user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0):
        raise ctypes.WinError(ctypes.get_last_error())
    rows.sort(key=lambda item: (not item["primary"], item["monitor"]["x"], item["monitor"]["y"]))
    for index, row in enumerate(rows):
        row["index"] = index
    return rows


def work_area(monitor: int = 0) -> dict[str, Any]:
    """按索引取显示器工作区；越界时抛 ValueError。"""
    rows = monitors()
    if not rows:
        raise ValueError("没有枚举到任何显示器。")
    if monitor is None:
        monitor = 0
    if not 0 <= int(monitor) < len(rows):
        raise ValueError(f"monitor 索引越界：{monitor}，当前共 {len(rows)} 个显示器。")
    return rows[int(monitor)]


def monitor_index_for_window(hwnd: int) -> int | None:
    handle = user32.MonitorFromWindow(_hwnd(hwnd), MONITOR_DEFAULTTOPRIMARY)
    if not handle:
        return None
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
        return None
    target = _rect_to_dict(info.rcMonitor)
    for row in monitors():
        if row["monitor"] == target:
            return row["index"]
    return None


def window_state(hwnd: int) -> str:
    if user32.IsIconic(_hwnd(hwnd)):
        return "minimized"
    if user32.IsZoomed(_hwnd(hwnd)):
        return "maximized"
    return "normal"


def _restore_for_layout(hwnd: int) -> None:
    if window_state(hwnd) != "normal":
        user32.ShowWindow(_hwnd(hwnd), SW_RESTORE)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and window_state(hwnd) != "normal":
            time.sleep(0.05)


def set_window_bounds(hwnd: int, x: int, y: int, width: int, height: int) -> dict[str, Any]:
    """把窗口的**可见外框**设到物理像素矩形，补偿 DWM 不可见边框。

    返回 applied_bounds 为真实回读值；与请求差值超过 4 像素时 clamped=true。
    """
    info = window_info(hwnd)
    if info is None:
        raise ValueError("窗口句柄无效或窗口已关闭。")
    if width <= 0 or height <= 0:
        raise ValueError("width、height 必须是正整数。")
    _restore_for_layout(hwnd)

    window_rect = RECT()
    if not user32.GetWindowRect(_hwnd(hwnd), ctypes.byref(window_rect)):
        raise ctypes.WinError(ctypes.get_last_error())
    visible = _dwm_rect(hwnd) or window_rect
    dx_left = int(visible.left - window_rect.left)
    dy_top = int(visible.top - window_rect.top)
    dx_right = int(window_rect.right - visible.right)
    dy_bottom = int(window_rect.bottom - visible.bottom)

    outer_x = int(x) - dx_left
    outer_y = int(y) - dy_top
    outer_width = int(width) + dx_left + dx_right
    outer_height = int(height) + dy_top + dy_bottom

    # DWM 边框补偿可能因取整差 1 像素；回读后用差值再校正，最多 3 轮。
    updated = info
    applied = info["rect"]
    for _attempt in range(3):
        if not user32.SetWindowPos(
            _hwnd(hwnd), None, outer_x, outer_y, outer_width, outer_height,
            SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(0.08)
        updated = window_info(hwnd)
        if updated is None:
            raise ValueError("窗口在调整后已关闭。")
        applied = updated["rect"]
        deltas = {
            "x": applied["x"] - int(x),
            "y": applied["y"] - int(y),
            "width": applied["width"] - int(width),
            "height": applied["height"] - int(height),
        }
        if all(value == 0 for value in deltas.values()):
            break
        outer_x -= deltas["x"]
        outer_y -= deltas["y"]
        outer_width -= deltas["width"]
        outer_height -= deltas["height"]
        if outer_width <= 0 or outer_height <= 0:
            break

    updated = window_info(hwnd) or info
    applied = updated["rect"]
    deltas = {
        "x": applied["x"] - int(x),
        "y": applied["y"] - int(y),
        "width": applied["width"] - int(width),
        "height": applied["height"] - int(height),
    }
    clamped = any(abs(value) > 4 for value in deltas.values())
    return {
        "window": updated,
        "requested_bounds": {"x": int(x), "y": int(y), "width": int(width), "height": int(height)},
        "applied_bounds": applied,
        "delta": deltas,
        "clamped": clamped,
        "state": window_state(hwnd),
    }


def tile_bounds(work: dict[str, int], tile: str) -> dict[str, int]:
    """按工作区计算并排矩形；左右各占一半，余数给右侧/下侧。"""
    x, y, width, height = work["x"], work["y"], work["width"], work["height"]
    half_w, half_h = width // 2, height // 2
    presets = {
        "left_half": (x, y, half_w, height),
        "right_half": (x + half_w, y, width - half_w, height),
        "top_left": (x, y, half_w, half_h),
        "top_right": (x + half_w, y, width - half_w, half_h),
        "bottom_left": (x, y + half_h, half_w, height - half_h),
        "bottom_right": (x + half_w, y + half_h, width - half_w, height - half_h),
    }
    if tile not in presets:
        raise ValueError(f"不支持的 tile：{tile}")
    left, top, tile_width, tile_height = presets[tile]
    return {"x": left, "y": top, "width": tile_width, "height": tile_height}


def set_window_state(hwnd: int, action: str) -> dict[str, Any]:
    """minimize / maximize / restore，并回读真实状态。"""
    commands = {"minimize": SW_MINIMIZE, "maximize": SW_MAXIMIZE, "restore": SW_RESTORE}
    if action not in commands:
        raise ValueError(f"不支持的状态操作：{action}")
    before = window_state(hwnd)
    if not user32.ShowWindow(_hwnd(hwnd), commands[action]):
        # ShowWindow 返回上一次的可见状态，false 不代表失败；继续回读确认。
        pass
    deadline = time.monotonic() + 2.0
    expected = {"minimize": "minimized", "maximize": "maximized", "restore": "normal"}[action]
    while time.monotonic() < deadline and window_state(hwnd) != expected:
        time.sleep(0.05)
    info = window_info(hwnd)
    if info is None:
        raise ValueError("窗口在状态切换后已关闭。")
    return {"action": action, "before": before, "state": window_state(hwnd), "window": info}


def close_window(hwnd: int, timeout: float = 2.0) -> dict[str, Any]:
    """发送 WM_CLOSE（等价点标题栏关闭），不杀进程；检测本次新出现的保存对话框。"""
    info = window_info(hwnd)
    if info is None:
        raise ValueError("窗口句柄无效或窗口已关闭。")
    pid = int(info["pid"])
    before_dialogs = {item["hwnd"] for item in dialog_windows(pid, hwnd)}
    if not user32.PostMessageW(_hwnd(hwnd), WM_CLOSE, 0, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    deadline = time.monotonic() + max(0.3, float(timeout))
    while time.monotonic() < deadline:
        if not user32.IsWindow(_hwnd(hwnd)):
            return {"closed": True, "close_pending_dialog": False, "window": info, "foreground": None, "dialogs": []}
        new_dialogs = [
            item for item in dialog_windows(pid, hwnd) if item["hwnd"] not in before_dialogs
        ]
        if new_dialogs:
            foreground = foreground_info()
            return {
                "closed": False,
                "close_pending_dialog": True,
                "window": window_info(hwnd) or info,
                "foreground": foreground,
                "dialogs": [
                    {"hwnd": item["hwnd"], "title": item["title"], "class": item["class"], "rect": item["rect"]}
                    for item in new_dialogs
                ],
                "message": "窗口仍在，检测到本次 WM_CLOSE 后新出现的保存对话框；未自动点击任何按钮。",
            }
        time.sleep(0.08)

    foreground = foreground_info()
    return {
        "closed": False,
        "close_pending_dialog": False,
        "window": window_info(hwnd) or info,
        "foreground": foreground,
        "dialogs": [],
        "message": "窗口仍在，未检测到新的同进程 #32770 对话框；可能未响应、被拦截或没有未保存内容。",
    }


# ---------------------------------------------------------------- 悬停与拖拽

MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
DRAG_BUTTONS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


def hover(
    x: int,
    y: int,
    duration_ms: int = 500,
    hwnd: int | None = None,
    expected_hwnd: int | None = None,
) -> dict[str, Any]:
    """把光标移到目标并停留，不按键；派发前后核对真实落点窗口。"""
    if not 0 <= int(duration_ms) <= 10000:
        raise ValueError("duration_ms 必须在 0~10000 之间。")
    screen_x, screen_y = resolve_click_point(int(x), int(y), hwnd)
    target = actual_target_at(screen_x, screen_y, expected_hwnd)
    if not user32.SetCursorPos(screen_x, screen_y):
        raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(int(duration_ms) / 1000.0)
    actual_target_at(screen_x, screen_y, expected_hwnd)
    return {
        "x": screen_x,
        "y": screen_y,
        "duration_ms": int(duration_ms),
        "cursor": current_cursor(),
        "target": target,
    }


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
    expected_hwnd: int | None = None,
) -> dict[str, Any]:
    """按下 → 插值移动 → 松开；每步检查落点窗口是否命中禁止清单。"""
    import security

    button = (button or "left").lower()
    if button not in DRAG_BUTTONS:
        raise ValueError("button 必须是 left、right 或 middle。")
    steps = int(steps)
    if not 2 <= steps <= 200:
        raise ValueError("steps 必须在 2~200 之间。")
    if not 0 <= int(hold_ms_before) <= 5000 or not 0 <= int(hold_ms_after) <= 5000:
        raise ValueError("hold_ms_before / hold_ms_after 必须在 0~5000 之间。")

    start_x, start_y = resolve_click_point(int(from_x), int(from_y), hwnd)
    end_x, end_y = resolve_click_point(int(to_x), int(to_y), hwnd)
    actual_target_at(start_x, start_y, expected_hwnd)
    down, up = DRAG_BUTTONS[button]
    step_delay = max(0.008, min(0.05, 0.15 / steps))

    if not user32.SetCursorPos(start_x, start_y):
        raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(int(hold_ms_before) / 1000.0)
    actual_target_at(start_x, start_y, expected_hwnd)
    _mouse_event(down)
    aborted = None
    actual_end = {"x": start_x, "y": start_y}
    try:
        for index in range(1, steps + 1):
            ratio = index / steps
            point_x = int(round(start_x + (end_x - start_x) * ratio))
            point_y = int(round(start_y + (end_y - start_y) * ratio))
            if not user32.SetCursorPos(point_x, point_y):
                raise ctypes.WinError(ctypes.get_last_error())
            actual_end = {"x": point_x, "y": point_y}
            time.sleep(step_delay)
            hit = window_at_point(point_x, point_y)
            reason = security.forbidden_reason(hit)
            if reason:
                aborted = {"reason": reason, "window": hit}
                break
        if not aborted:
            final_target = window_at_point(actual_end["x"], actual_end["y"])
            reason = security.forbidden_reason(final_target)
            if reason:
                aborted = {"reason": reason, "window": final_target}
        if not aborted:
            time.sleep(int(hold_ms_after) / 1000.0)
    finally:
        _mouse_event(up)

    result: dict[str, Any] = {
        "button": button,
        "steps": steps,
        "start": {"x": start_x, "y": start_y},
        "end": actual_end,
        "requested_end": {"x": end_x, "y": end_y},
        "cursor": current_cursor(),
        "target": window_at_point(actual_end["x"], actual_end["y"]),
    }
    if aborted:
        result["aborted_blocked_window"] = True
        result["aborted_reason"] = aborted["reason"]
        result["blocked_window"] = aborted["window"]
    else:
        result["aborted_blocked_window"] = False
    return result


# ---------------------------------------------------------------- 原始画面抓取

def grab_image(
    hwnd: int | None = None,
    region: dict[str, int] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """抓取屏幕/客户区/指定区域原图（不缩放），返回 (PIL.Image, metadata)。

    region 使用**屏幕物理像素绝对坐标** {x,y,width,height}；hwnd 客户区截图
    使用屏幕上的客户区矩形（可见即所得），origin 为左上角。
    """
    from PIL import ImageGrab

    if region is not None:
        x, y = int(region["x"]), int(region["y"])
        width, height = int(region["width"]), int(region["height"])
        if width <= 0 or height <= 0:
            raise ValueError("region 的 width、height 必须是正整数。")
        if _outside_virtual_screen(x, y) or _outside_virtual_screen(x + width - 1, y + height - 1):
            raise ValueError("region 超出当前虚拟屏幕。")
        image = ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)
        origin = {"x": x, "y": y}
        mode = "region"
        label = None
    elif hwnd is not None:
        hwnd = int(hwnd)
        info = window_info(hwnd)
        if info is None:
            raise ValueError("窗口句柄无效或窗口已关闭。")
        if info["minimized"]:
            raise ValueError("窗口已最小化，先调用 focus_window 或 manage_window(restore) 后再截图。")
        client = client_metrics(hwnd)
        image = ImageGrab.grab(
            bbox=(client["x"], client["y"], client["x"] + client["width"], client["y"] + client["height"]),
            all_screens=True,
        )
        origin = {"x": client["x"], "y": client["y"]}
        mode = "window"
        label = hwnd
    else:
        metrics = screen_metrics()
        image = ImageGrab.grab(all_screens=True)
        origin = {"x": metrics["x"], "y": metrics["y"]}
        mode = "screen"
        label = None

    metadata = {
        "mode": mode,
        "hwnd": label,
        "origin": origin,
        "width": int(image.width),
        "height": int(image.height),
        "original_width": int(image.width),
        "original_height": int(image.height),
        "scale": 1.0,
    }
    return image, metadata


def image_fingerprint(image: Any, max_width: int = 160) -> tuple[str, bytes]:
    """把图像缩成灰度缩略图，返回短哈希与原始缩略字节，供稳定度比较。"""
    gray = image.convert("L")
    if gray.width > max_width:
        height = max(1, round(gray.height * max_width / gray.width))
        gray = gray.resize((max_width, height), resample=1)  # BILINEAR
    raw = gray.tobytes()
    return hashlib.sha256(raw).hexdigest()[:16], raw


def image_diff_ratio(previous: bytes, current: bytes, pixel_threshold: int = 8) -> float:
    """两帧灰度缩略图的差异像素比例。"""
    if not previous or len(previous) != len(current):
        return 1.0
    changed = sum(1 for a, b in zip(previous, current) if abs(a - b) > pixel_threshold)
    return changed / max(1, len(current))


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
    capture_method = "screen"
    if hwnd is not None:
        hwnd = int(hwnd)
        info = window_info(hwnd)
        if info is None:
            raise ValueError("窗口句柄无效或窗口已关闭。")
        if info["minimized"]:
            raise ValueError("窗口已最小化，先调用 focus_window 还原后再截图。")
        client = client_metrics(hwnd)

        def grab_client_screen():
            captured = ImageGrab.grab(
                bbox=(client["x"], client["y"], client["x"] + client["width"], client["y"] + client["height"]),
                all_screens=True,
            )
            if captured.size != (client["width"], client["height"]):
                raise ValueError(
                    f"客户区截图尺寸 {captured.size} 与客户区 "
                    f"{client['width']}x{client['height']} 不一致。"
                )
            return captured

        capture_method = "window-print"
        try:
            image = ImageGrab.grab(window=hwnd)
        except (OSError, TypeError, AttributeError):
            # Pillow < 11.2.1 不支持 window 参数；退化为屏幕客户区，保持坐标契约。
            image = grab_client_screen()
            capture_method = "window-screen"
        else:
            frame = info["rect"]
            if image.size != (client["width"], client["height"]):
                left = client["x"] - frame["x"]
                top = client["y"] - frame["y"]
                box = (left, top, left + client["width"], top + client["height"])
                if (
                    left >= 0
                    and top >= 0
                    and box[2] <= image.width
                    and box[3] <= image.height
                    and image.crop(box).size == (client["width"], client["height"])
                ):
                    image = image.crop(box)
                else:
                    image = grab_client_screen()
                    capture_method = "window-screen"
            if image.size != (client["width"], client["height"]):
                raise ValueError(
                    f"窗口截图尺寸 {image.size} 与客户区 "
                    f"{client['width']}x{client['height']} 不一致，拒绝返回错误坐标元数据。"
                )
            gray = image.convert("L")
            low, high = gray.getextrema()
            # Chrome / Electron 等窗口的 PrintWindow 可能返回纯白；此时改抓屏幕客户区。
            if high - low < 3:
                image = grab_client_screen()
                capture_method = "window-screen"
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
        "capture_method": capture_method,
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


# ---------------------------------------------------------------- 输入注入

ULONG_PTR = ctypes.c_ulonglong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", w.WORD),
        ("wScan", w.WORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", w.LONG),
        ("dy", w.LONG),
        ("mouseData", w.DWORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", w.DWORD), ("wParamL", w.WORD), ("wParamH", w.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("u", _INPUTUNION)]


user32.SendInput.restype = w.UINT
user32.SendInput.argtypes = [w.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SetCursorPos.restype = w.BOOL
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.VkKeyScanW.restype = ctypes.c_short
user32.VkKeyScanW.argtypes = [w.WCHAR]

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

VK_NAMES = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "insert": 0x2D,
    "ins": 0x2D,
    "delete": 0x2E,
    "del": 0x2E,
    "win": 0x5B,
    "windows": 0x5B,
    "lwin": 0x5B,
    "rwin": 0x5C,
    "apps": 0x5D,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    "numlock": 0x90,
    "scrolllock": 0x91,
}
for _index in range(1, 25):
    VK_NAMES[f"f{_index}"] = 0x6F + _index
for _char in "0123456789":
    VK_NAMES[_char] = ord(_char)
for _char in "abcdefghijklmnopqrstuvwxyz":
    VK_NAMES[_char] = ord(_char.upper())
PUNCTUATION_VK = {
    ";": 0xBA,
    "=": 0xBB,
    ",": 0xBC,
    "-": 0xBD,
    ".": 0xBE,
    "/": 0xBF,
    "`": 0xC0,
    "[": 0xDB,
    "\\": 0xDC,
    "]": 0xDD,
    "'": 0xDE,
}


def _send_input(inp: INPUT) -> None:
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise OSError(ctypes.get_last_error(), "SendInput 失败，目标窗口可能以更高权限运行。")


def _key_event(vk: int = 0, scan: int = 0, flags: int = 0) -> None:
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.u.ki = KEYBDINPUT(int(vk), int(scan), int(flags), 0, 0)
    _send_input(inp)


def _mouse_event(flags: int, data: int = 0) -> None:
    inp = INPUT(type=INPUT_MOUSE)
    inp.u.mi = MOUSEINPUT(0, 0, int(data) & 0xFFFFFFFF, int(flags), 0, 0)
    _send_input(inp)


def _outside_virtual_screen(x: int, y: int) -> bool:
    metrics = screen_metrics()
    return not (
        metrics["x"] <= x < metrics["x"] + metrics["width"]
        and metrics["y"] <= y < metrics["y"] + metrics["height"]
    )


def resolve_click_point(x: int, y: int, hwnd: int | None = None) -> tuple[int, int]:
    """把屏幕坐标或窗口客户区坐标解析成屏幕物理坐标。"""
    if hwnd is not None:
        client = client_metrics(int(hwnd))
        if not (0 <= x < client["width"] and 0 <= y < client["height"]):
            raise ValueError(
                f"坐标超出窗口客户区：x={x}, y={y}, 客户区={client['width']}x{client['height']}。"
            )
        screen_x, screen_y = client["x"] + x, client["y"] + y
    else:
        screen_x, screen_y = int(x), int(y)
    if _outside_virtual_screen(screen_x, screen_y):
        raise ValueError(f"坐标 ({screen_x}, {screen_y}) 不在当前虚拟屏幕内。")
    return screen_x, screen_y


def click(
    x: int,
    y: int,
    button: str = "left",
    double: bool = False,
    hwnd: int | None = None,
    expected_hwnd: int | None = None,
) -> dict[str, Any]:
    """点击物理像素坐标；hwnd 存在时 x/y 相对客户区左上角。"""
    button = (button or "left").lower()
    if button not in ("left", "right"):
        raise ValueError("button 必须是 left 或 right。")
    screen_x, screen_y = resolve_click_point(x, y, hwnd)
    target = actual_target_at(screen_x, screen_y, expected_hwnd)
    if not user32.SetCursorPos(int(screen_x), int(screen_y)):
        raise ctypes.WinError(ctypes.get_last_error())
    down, up = (
        (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
        if button == "left"
        else (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
    )
    clicks = 2 if double else 1
    for index in range(clicks):
        actual_target_at(screen_x, screen_y, expected_hwnd)
        _mouse_event(down)
        _mouse_event(up)
        if index + 1 < clicks:
            time.sleep(0.08)
    return {
        "x": int(screen_x),
        "y": int(screen_y),
        "button": button,
        "double": bool(double),
        "cursor": current_cursor(),
        "target": target,
    }


def scroll(
    clicks: int = 3,
    x: int | None = None,
    y: int | None = None,
    expected_hwnd: int | None = None,
) -> dict[str, Any]:
    """滚动鼠标滚轮；clicks 正数向上、负数向下。"""
    if clicks == 0:
        raise ValueError("clicks 不能为 0。")
    if (x is None) != (y is None):
        raise ValueError("x 和 y 必须同时提供或同时省略。")
    if x is not None:
        if _outside_virtual_screen(int(x), int(y)):
            raise ValueError(f"坐标 ({x}, {y}) 不在当前虚拟屏幕内。")
        if not user32.SetCursorPos(int(x), int(y)):
            raise ctypes.WinError(ctypes.get_last_error())
    cursor = current_cursor()
    target = actual_target_at(cursor["x"], cursor["y"], expected_hwnd)
    actual_target_at(cursor["x"], cursor["y"], expected_hwnd)
    _mouse_event(MOUSEEVENTF_WHEEL, int(clicks) * WHEEL_DELTA)
    return {
        "clicks": int(clicks),
        "delta": int(clicks) * WHEEL_DELTA,
        "cursor": cursor,
        "target": target,
    }


def _vk_for_token(token: str) -> tuple[int, bool]:
    """返回 (VK, 是否需要 shift)。未知键抛 ValueError。"""
    token = token.strip().lower()
    if not token:
        raise ValueError("组合键中有空键位。")
    if token in VK_NAMES:
        return VK_NAMES[token], False
    if token in PUNCTUATION_VK:
        return PUNCTUATION_VK[token], False
    if len(token) == 1:
        scan = user32.VkKeyScanW(token)
        if scan != -1:
            vk = scan & 0xFF
            shift = bool((scan >> 8) & 0x01)
            return vk, shift
    raise ValueError(f"不认识的按键：{token}")


def _ensure_foreground(expected_hwnd: int | None) -> None:
    if expected_hwnd is None:
        return
    current = int(user32.GetForegroundWindow() or 0)
    if current != int(expected_hwnd):
        raise ValueError(
            f"target_changed：前台窗口已变为 hwnd {current}，与预期 {expected_hwnd} 不一致，已中止输入。"
        )


def press_keys(keys: str, expected_hwnd: int | None = None) -> dict[str, Any]:
    """按组合键，例如 ctrl+v、alt+tab、win+d。"""
    if not isinstance(keys, str) or not keys.strip():
        raise ValueError("keys 不能为空。")
    tokens = [part.strip().lower() for part in keys.split("+")]
    if any(not part for part in tokens):
        raise ValueError("组合键格式无效，例如应为 ctrl+v。")
    parsed = [_vk_for_token(token) for token in tokens]
    pressed: list[int] = []
    try:
        for vk, shift in parsed:
            _ensure_foreground(expected_hwnd)
            if shift:
                _key_event(VK_NAMES["shift"])
                pressed.append(VK_NAMES["shift"])
            _key_event(vk)
            pressed.append(vk)
    finally:
        # 出错时也释放已按下的键，避免系统卡在修饰键状态。
        for vk in reversed(pressed):
            _key_event(vk, flags=KEYEVENTF_KEYUP)
    return {"keys": keys.strip(), "vk": [vk for vk, _ in parsed]}


def type_text(text: str, expected_hwnd: int | None = None) -> dict[str, Any]:
    """用 SendInput Unicode 输入文本；不写剪贴板。"""
    if not isinstance(text, str) or text == "":
        raise ValueError("text 不能为空。")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    units = 0
    newlines = 0
    for char in normalized:
        _ensure_foreground(expected_hwnd)
        if char == "\n":
            _key_event(0x0D)
            _key_event(0x0D, flags=KEYEVENTF_KEYUP)
            newlines += 1
        elif char == "\t":
            _key_event(0x09)
            _key_event(0x09, flags=KEYEVENTF_KEYUP)
        else:
            data = char.encode("utf-16-le")
            for index in range(0, len(data), 2):
                unit = int.from_bytes(data[index:index + 2], "little")
                _key_event(0, unit, KEYEVENTF_UNICODE)
                _key_event(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)
                units += 1
    return {
        "characters": len(normalized),
        "utf16_units": units,
        "newlines": newlines,
    }


def foreground_info() -> dict[str, Any] | None:
    hwnd = int(user32.GetForegroundWindow() or 0)
    return window_info(hwnd) if hwnd else None
