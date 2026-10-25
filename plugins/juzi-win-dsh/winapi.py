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
    capture_method = "screen"
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
        # Chrome / Electron 等窗口的 PrintWindow 可能返回纯白；此时改抓屏幕客户区。
        gray = image.convert("L")
        low, high = gray.getextrema()
        capture_method = "window-print"
        if high - low < 3:
            image = ImageGrab.grab(bbox=(
                client["x"], client["y"], client["x"] + client["width"], client["y"] + client["height"]
            ))
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
) -> dict[str, Any]:
    """点击物理像素坐标；hwnd 存在时 x/y 相对客户区左上角。"""
    button = (button or "left").lower()
    if button not in ("left", "right"):
        raise ValueError("button 必须是 left 或 right。")
    screen_x, screen_y = resolve_click_point(x, y, hwnd)
    target = window_at_point(screen_x, screen_y)
    if not user32.SetCursorPos(int(screen_x), int(screen_y)):
        raise ctypes.WinError(ctypes.get_last_error())
    down, up = (
        (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
        if button == "left"
        else (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
    )
    clicks = 2 if double else 1
    for index in range(clicks):
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
    target = window_at_point(cursor["x"], cursor["y"])
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


def press_keys(keys: str) -> dict[str, Any]:
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


def type_text(text: str) -> dict[str, Any]:
    """用 SendInput Unicode 输入文本；不写剪贴板。"""
    if not isinstance(text, str) or text == "":
        raise ValueError("text 不能为空。")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    units = 0
    newlines = 0
    for char in normalized:
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
