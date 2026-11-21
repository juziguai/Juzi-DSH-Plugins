#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 专属桌面悬浮游标（Figma 协作者式透明穿透层）。

生命周期铁律：仅在 AI 正在执行物理桌面操作期间展示，调用收工即刻隐藏，闲置绝不驻留。
1. 纯标准库 ctypes + Pillow 预烘焙抗锯齿图层，绝不调用 SetSystemCursor 修改用户系统鼠标设置；
2. WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE：
   100% 物理点击穿透、不抢焦点、不进任务栏、不干扰 window_at_point 落点校验；
3. SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)：人眼可见，screenshot / OCR / WGC 自动隐身；
4. 独立后台 GUI 线程 + 非阻塞状态投递：对工具调用增加 0ms 延迟，收工立即 SW_HIDE（0% CPU）。
"""

from __future__ import annotations

import atexit
from contextlib import contextmanager
import ctypes
from ctypes import wintypes as w
import os
import threading
import time
from typing import Any, Iterator

CANVAS_SIZE = 128
HOTSPOT_X = 38
HOTSPOT_Y = 38
RIPPLE_FRAMES = 10
RIPPLE_DURATION_S = 0.20  # 瞬发单次点击仅闪 200ms 波纹即刻消失，不拖泥带水

WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

SW_HIDE = 0
HWND_TOPMOST = w.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0
BI_RGB = 0
WDA_EXCLUDEFROMCAPTURE = 0x00000011

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113
WM_APP_WAKE = 0x8001
TIMER_ID = 1
FRAME_INTERVAL_MS = 16


def _is_enabled() -> bool:
    raw = os.environ.get("JUZI_WIN_DSH_CURSOR", "on").strip().lower()
    return raw not in ("0", "off", "false", "no", "disabled")


class POINT(ctypes.Structure):
    _fields_ = [("x", w.LONG), ("y", w.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", w.LONG), ("cy", w.LONG)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", w.DWORD),
        ("biWidth", w.LONG),
        ("biHeight", w.LONG),
        ("biPlanes", w.WORD),
        ("biBitCount", w.WORD),
        ("biCompression", w.DWORD),
        ("biSizeImage", w.DWORD),
        ("biXPelsPerMeter", w.LONG),
        ("biYPelsPerMeter", w.LONG),
        ("biClrUsed", w.DWORD),
        ("biClrImportant", w.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.UINT),
        ("style", w.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", w.HINSTANCE),
        ("hIcon", w.HICON),
        ("hCursor", w.HANDLE),
        ("hbrBackground", w.HBRUSH),
        ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR),
        ("hIconSm", w.HICON),
    ]


def _render_frames() -> tuple[bytes, list[bytes], bytes]:
    """2x 超采样预渲染：按系统 SM_CXCURSOR 自适应 1:1 匹配 Windows 原生默认箭头尺寸。
    在 150% DPI (SM_CXCURSOR=48) 下：箭头总高 28 px × 宽 18 px，[● AI] 胶囊 27×14 px。
    """
    from PIL import Image, ImageDraw, ImageFilter

    try:
        sys_cx = int(ctypes.windll.user32.GetSystemMetrics(13))  # SM_CXCURSOR (48 @ 150% DPI)
        dpi_scale = max(0.65, min(2.0, sys_cx / 48.0)) if sys_cx > 0 else 1.0
    except Exception:  # noqa: BLE001
        dpi_scale = 1.0

    ss = 2
    full = CANVAS_SIZE * ss
    hx, hy = HOTSPOT_X * ss, HOTSPOT_Y * ss

    def make_arrow_layer(scale_arrow: float = 1.0, badge_accent: tuple[int, int, int] = (56, 189, 248)) -> Any:
        s = dpi_scale * scale_arrow
        # 2x 超采样基准：总高 56 (物理 28px @ 150% DPI)，与 Windows aero_arrow 1:1 对齐
        raw_pts = [
            (0, 0),
            (0, 50),
            (12, 39),
            (20, 56),
            (28, 52),
            (20, 35),
            (36, 35),
        ]
        poly = [(hx + int(round(px * s)), hy + int(round(py * s))) for px, py in raw_pts]

        shadow = Image.new("RGBA", (full, full), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow)
        shifted = [(px + 3, py + 4) for px, py in poly]
        sdraw.polygon(shifted, fill=(0, 0, 0, 100))

        bx = hx + int(round(34 * dpi_scale))
        by = hy + int(round(46 * dpi_scale))
        bw = int(round(54 * dpi_scale))
        bh = int(round(28 * dpi_scale))
        rad = bh // 2
        sdraw.rounded_rectangle((bx + 2, by + 4, bx + bw + 2, by + bh + 4), radius=rad, fill=(0, 0, 0, 90))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3.0))

        fg = Image.new("RGBA", (full, full), (0, 0, 0, 0))
        draw = ImageDraw.Draw(fg)

        border_w = max(5, int(round(7 * s)))
        draw.line(poly + [poly[0]], fill=(255, 255, 255, 255), width=border_w, joint="curve")
        draw.polygon(poly, fill=(16, 18, 23, 255))

        draw.rounded_rectangle(
            (bx, by, bx + bw, by + bh),
            radius=rad,
            fill=(18, 21, 28, 244),
            outline=(255, 255, 255, 235),
            width=max(2, int(round(2.5 * dpi_scale))),
        )
        dot_r = max(3, int(round(4 * dpi_scale)))
        dcx, dcy = bx + int(round(12 * dpi_scale)), by + bh // 2
        draw.ellipse((dcx - dot_r, dcy - dot_r, dcx + dot_r, dcy + dot_r), fill=(*badge_accent, 255))

        ax = bx + int(round(21 * dpi_scale))
        ay = by + int(round(7 * dpi_scale))
        ah = int(round(14 * dpi_scale))
        aw = int(round(12 * dpi_scale))
        sw_line = max(2, int(round(3 * dpi_scale)))
        # 'A'
        draw.line([(ax, ay + ah), (ax + aw // 2, ay), (ax + aw, ay + ah)], fill=(255, 255, 255, 255), width=sw_line, joint="curve")
        draw.line([(ax + 2, ay + int(ah * 0.65)), (ax + aw - 2, ay + int(ah * 0.65))], fill=(255, 255, 255, 255), width=max(2, sw_line - 1))
        # 'I'
        ix = ax + aw + int(round(7 * dpi_scale))
        ibar = max(2, int(round(3 * dpi_scale)))
        draw.line([(ix, ay), (ix, ay + ah)], fill=(255, 255, 255, 255), width=sw_line)
        draw.line([(ix - ibar, ay), (ix + ibar, ay)], fill=(255, 255, 255, 235), width=max(2, sw_line - 1))
        draw.line([(ix - ibar, ay + ah), (ix + ibar, ay + ah)], fill=(255, 255, 255, 235), width=max(2, sw_line - 1))

        return Image.alpha_composite(shadow, fg)

    def to_bgra(img_2x: Any) -> bytes:
        down = img_2x.resize((CANVAS_SIZE, CANVAS_SIZE), resample=3)
        return down.convert("RGBa").tobytes("raw", "BGRa")

    normal_2x = make_arrow_layer(scale_arrow=1.0, badge_accent=(56, 189, 248))
    pressed_2x = make_arrow_layer(scale_arrow=0.90, badge_accent=(52, 211, 153))

    ripples: list[bytes] = []
    for idx in range(1, RIPPLE_FRAMES + 1):
        t = idx / float(RIPPLE_FRAMES)
        ease = 1.0 - (1.0 - t) * (1.0 - t)
        radius = int(round((10 + 34 * ease) * dpi_scale))
        alpha = int(round(225 * ((1.0 - t) ** 1.3)))
        ring = Image.new("RGBA", (full, full), (0, 0, 0, 0))
        rdraw = ImageDraw.Draw(ring)
        if alpha > 8:
            rdraw.ellipse(
                (hx - radius, hy - radius, hx + radius, hy + radius),
                outline=(56, 189, 248, alpha),
                width=max(4, int(round(5 * dpi_scale))),
            )
            inner_r = max(3, radius - int(round(5 * dpi_scale)))
            rdraw.ellipse(
                (hx - inner_r, hy - inner_r, hx + inner_r, hy + inner_r),
                outline=(255, 255, 255, alpha // 2),
                width=max(2, int(round(2.5 * dpi_scale))),
            )
        arrow_src = pressed_2x if idx <= 2 else normal_2x
        composed = Image.alpha_composite(ring, arrow_src)
        ripples.append(to_bgra(composed))

    return to_bgra(normal_2x), ripples, to_bgra(pressed_2x)


class CursorOverlay:
    """后台线程驱动的 Win32 分层穿透游标窗口（严格随操作生命周期显隐）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = False
        self._closed = False
        self._hwnd: int = 0
        self._thread: threading.Thread | None = None

        self._active_depth = 0
        self._has_pos = False
        self._x = 0
        self._y = 0
        self._pressed = False
        self._ripple_start = 0.0

    def _ensure_started(self) -> bool:
        if not _is_enabled() or self._closed:
            return False
        with self._lock:
            if self._started:
                return True
            self._started = True
            thread = threading.Thread(target=self._gui_loop, name="juzi-cursor-overlay", daemon=True)
            self._thread = thread
            thread.start()
        return True

    def _wake(self) -> None:
        hwnd = self._hwnd
        if hwnd:
            ctypes.windll.user32.PostMessageW(w.HWND(hwnd), WM_APP_WAKE, 0, 0)

    def begin_work(self, x: int | None = None, y: int | None = None) -> None:
        if not self._ensure_started():
            return
        with self._lock:
            self._active_depth += 1
            if x is not None and y is not None:
                self._x = int(x)
                self._y = int(y)
                self._has_pos = True
        if x is not None and y is not None:
            self._wake()

    def end_work(self) -> None:
        with self._lock:
            self._active_depth = max(0, self._active_depth - 1)
            self._pressed = False
        self._wake()

    @contextmanager
    def work_scope(self, x: int | None = None, y: int | None = None) -> Iterator[None]:
        self.begin_work(x, y)
        try:
            yield
        finally:
            self.end_work()

    def notify_move(self, x: int, y: int, *, pressed: bool = False, hold_ms: int = 0) -> None:
        del hold_ms
        if not self._ensure_started():
            return
        with self._lock:
            self._x = int(x)
            self._y = int(y)
            self._has_pos = True
            self._pressed = bool(pressed)
        self._wake()

    def notify_click(self, x: int, y: int, *, button: str = "left", double: bool = False) -> None:
        del button, double
        if not self._ensure_started():
            return
        now = time.monotonic()
        with self._lock:
            self._x = int(x)
            self._y = int(y)
            self._has_pos = True
            self._pressed = False
            self._ripple_start = now
        self._wake()

    def notify_scroll(self, x: int, y: int, *, clicks: int = 3) -> None:
        del clicks
        self.notify_click(x, y)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._active_depth = 0
            hwnd = self._hwnd
        if hwnd:
            try:
                ctypes.windll.user32.PostMessageW(w.HWND(hwnd), WM_CLOSE, 0, 0)
            except Exception:  # noqa: BLE001
                pass

    def _gui_loop(self) -> None:
        try:
            normal_buf, ripple_bufs, pressed_buf = _render_frames()
        except Exception:  # noqa: BLE001
            return

        # 使用独立 WinDLL 实例，避免污染进程全局 ctypes.windll.user32 的 argtypes
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        u32.DefWindowProcW.restype = ctypes.c_ssize_t
        u32.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        u32.CreateWindowExW.restype = w.HWND
        u32.CreateWindowExW.argtypes = [
            w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID,
        ]
        u32.UpdateLayeredWindow.restype = w.BOOL
        u32.UpdateLayeredWindow.argtypes = [
            w.HWND, w.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
            w.HDC, ctypes.POINTER(POINT), w.COLORREF, ctypes.POINTER(BLENDFUNCTION), w.DWORD,
        ]
        u32.GetDC.restype = w.HDC
        u32.GetDC.argtypes = [w.HWND]
        u32.ReleaseDC.restype = ctypes.c_int
        u32.ReleaseDC.argtypes = [w.HWND, w.HDC]
        u32.SetTimer.restype = ctypes.c_size_t
        u32.SetTimer.argtypes = [w.HWND, ctypes.c_size_t, w.UINT, ctypes.c_void_p]
        u32.KillTimer.restype = w.BOOL
        u32.KillTimer.argtypes = [w.HWND, ctypes.c_size_t]
        u32.ShowWindow.restype = w.BOOL
        u32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
        u32.SetWindowPos.restype = w.BOOL
        u32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.UINT]
        u32.DestroyWindow.restype = w.BOOL
        u32.DestroyWindow.argtypes = [w.HWND]
        u32.SetWindowDisplayAffinity.restype = w.BOOL
        u32.SetWindowDisplayAffinity.argtypes = [w.HWND, w.DWORD]
        u32.RegisterClassExW.restype = w.ATOM
        u32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
        u32.GetMessageW.restype = w.BOOL
        u32.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
        u32.TranslateMessage.restype = w.BOOL
        u32.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
        u32.DispatchMessageW.restype = ctypes.c_ssize_t
        u32.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]
        k32.GetModuleHandleW.restype = w.HMODULE
        k32.GetModuleHandleW.argtypes = [w.LPCWSTR]
        gdi32.CreateCompatibleDC.restype = w.HDC
        gdi32.CreateCompatibleDC.argtypes = [w.HDC]
        gdi32.CreateDIBSection.restype = w.HBITMAP
        gdi32.CreateDIBSection.argtypes = [
            w.HDC, ctypes.POINTER(BITMAPINFO), w.UINT,
            ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD,
        ]
        gdi32.SelectObject.restype = w.HGDIOBJ
        gdi32.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
        gdi32.DeleteObject.restype = w.BOOL
        gdi32.DeleteObject.argtypes = [w.HGDIOBJ]
        gdi32.DeleteDC.restype = w.BOOL
        gdi32.DeleteDC.argtypes = [w.HDC]

        screen_dc = u32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = CANVAS_SIZE
        bmi.bmiHeader.biHeight = -CANVAS_SIZE
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits_ptr = ctypes.c_void_p()
        dib = gdi32.CreateDIBSection(screen_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits_ptr), None, 0)
        u32.ReleaseDC(None, screen_dc)
        if not dib or not bits_ptr.value:
            if mem_dc:
                gdi32.DeleteDC(mem_dc)
            return
        old_bmp = gdi32.SelectObject(mem_dc, dib)
        byte_len = CANVAS_SIZE * CANVAS_SIZE * 4

        state = {"shown": False, "timer": False, "last_buf": None}

        def paint_tick(hwnd_val: w.HWND) -> None:
            now = time.monotonic()
            with self._lock:
                active = self._active_depth > 0
                has_pos = self._has_pos
                tx, ty = self._x, self._y
                pressed = self._pressed
                ripple_start = self._ripple_start

            ripple_elapsed = now - ripple_start
            in_ripple = 0.0 <= ripple_elapsed < RIPPLE_DURATION_S
            should_show = has_pos and (active or in_ripple)

            if not should_show:
                if state["timer"]:
                    u32.KillTimer(hwnd_val, TIMER_ID)
                    state["timer"] = False
                if state["shown"]:
                    u32.ShowWindow(hwnd_val, SW_HIDE)
                    state["shown"] = False
                return

            if in_ripple:
                idx = min(RIPPLE_FRAMES - 1, int((ripple_elapsed / RIPPLE_DURATION_S) * RIPPLE_FRAMES))
                buf = ripple_bufs[idx]
            elif pressed:
                buf = pressed_buf
            else:
                buf = normal_buf

            if state["last_buf"] is not buf:
                ctypes.memmove(bits_ptr.value, buf, byte_len)
                state["last_buf"] = buf

            dst_pt = POINT(tx - HOTSPOT_X, ty - HOTSPOT_Y)
            wnd_size = SIZE(CANVAS_SIZE, CANVAS_SIZE)
            src_pt = POINT(0, 0)
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
            u32.UpdateLayeredWindow(
                hwnd_val, None, ctypes.byref(dst_pt), ctypes.byref(wnd_size),
                mem_dc, ctypes.byref(src_pt), 0, ctypes.byref(blend), ULW_ALPHA,
            )
            if not state["shown"]:
                u32.SetWindowPos(
                    hwnd_val, HWND_TOPMOST, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
                )
                state["shown"] = True

            if in_ripple and not state["timer"]:
                u32.SetTimer(hwnd_val, TIMER_ID, FRAME_INTERVAL_MS, None)
                state["timer"] = True
            elif not in_ripple and state["timer"]:
                u32.KillTimer(hwnd_val, TIMER_ID)
                state["timer"] = False

        @WNDPROC
        def wnd_proc(hwnd_val: w.HWND, msg: int, wparam: int, lparam: int) -> int:
            if msg in (WM_APP_WAKE, WM_TIMER):
                paint_tick(hwnd_val)
                return 0
            if msg == WM_CLOSE:
                if state["timer"]:
                    u32.KillTimer(hwnd_val, TIMER_ID)
                    state["timer"] = False
                u32.DestroyWindow(hwnd_val)
                return 0
            if msg == WM_DESTROY:
                u32.PostQuitMessage(0)
                return 0
            return u32.DefWindowProcW(hwnd_val, msg, wparam, lparam)

        self._wnd_proc_ref = wnd_proc
        hinst = k32.GetModuleHandleW(None)
        class_name = f"JuziAiCursorOverlay_{os.getpid()}"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = wnd_proc
        wc.hInstance = hinst
        wc.lpszClassName = class_name
        u32.RegisterClassExW(ctypes.byref(wc))

        ex_style = WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        hwnd = u32.CreateWindowExW(
            ex_style, class_name, "Juzi AI Cursor", WS_POPUP,
            0, 0, CANVAS_SIZE, CANVAS_SIZE, None, None, hinst, None,
        )
        if not hwnd:
            gdi32.SelectObject(mem_dc, old_bmp)
            gdi32.DeleteObject(dib)
            gdi32.DeleteDC(mem_dc)
            return

        try:
            u32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        except Exception:  # noqa: BLE001
            pass

        self._hwnd = int(hwnd)
        paint_tick(hwnd)

        msg = w.MSG()
        try:
            while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                u32.TranslateMessage(ctypes.byref(msg))
                u32.DispatchMessageW(ctypes.byref(msg))
        finally:
            self._hwnd = 0
            gdi32.SelectObject(mem_dc, old_bmp)
            gdi32.DeleteObject(dib)
            gdi32.DeleteDC(mem_dc)


_overlay = CursorOverlay()
begin_work = _overlay.begin_work
end_work = _overlay.end_work
work_scope = _overlay.work_scope
notify_move = _overlay.notify_move
notify_click = _overlay.notify_click
notify_scroll = _overlay.notify_scroll
close = _overlay.close
atexit.register(close)
