#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""剪贴板文本事务（纯 ctypes，标准库实现）。

只保证 CF_UNICODETEXT。写入前必须成功取得快照（成功/确实为空），备份失败不写；
写入后记录剪贴板序列号作为所有权标记，restore 前发现外部新内容就返回冲突而不是覆盖。
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes as w
from typing import Any

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

user32.OpenClipboard.restype = w.BOOL
user32.OpenClipboard.argtypes = [w.HWND]
user32.CloseClipboard.restype = w.BOOL
user32.CloseClipboard.argtypes = []
user32.EmptyClipboard.restype = w.BOOL
user32.EmptyClipboard.argtypes = []
user32.IsClipboardFormatAvailable.restype = w.BOOL
user32.IsClipboardFormatAvailable.argtypes = [w.UINT]
user32.GetClipboardData.restype = ctypes.c_void_p
user32.GetClipboardData.argtypes = [w.UINT]
user32.SetClipboardData.restype = ctypes.c_void_p
user32.SetClipboardData.argtypes = [w.UINT, ctypes.c_void_p]
user32.GetClipboardSequenceNumber.restype = w.DWORD
user32.GetClipboardSequenceNumber.argtypes = []

kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
kernel32.GlobalFree.restype = ctypes.c_void_p
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = w.BOOL
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

# 单槽事务快照：最近一次 set/clear 之前的文本 + 本次写入后的序列号。
_backup: dict[str, Any] | None = None
_LOCK = threading.Lock()


class ClipboardError(RuntimeError):
    pass


def _open(retries: int = 12) -> None:
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.05)
    raise ClipboardError("无法打开剪贴板：可能被其他程序长时间占用。")


def _close() -> None:
    try:
        user32.CloseClipboard()
    except OSError:
        pass


def _sequence() -> int:
    return int(user32.GetClipboardSequenceNumber())


def _stable_sequence(initial: int, timeout: float = 2.0, settle: float = 0.45) -> int:
    """等待本次写入引发的系统格式/剪贴板管理器变更稳定，返回最终序列号。"""
    current = int(initial)
    last_change = time.monotonic()
    deadline = last_change + timeout
    while time.monotonic() < deadline:
        time.sleep(0.05)
        latest = _sequence()
        if latest != current:
            current = latest
            last_change = time.monotonic()
        elif time.monotonic() - last_change >= settle:
            break
    return current


def _snapshot_unlocked() -> dict[str, Any]:
    """在已持有 _LOCK 的前提下读取文本快照；失败抛异常，空剪贴板返回 empty。"""
    for _attempt in range(4):
        _open()
        try:
            before = _sequence()
            if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return {"status": "empty", "text": None, "sequence": before}
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                raise ClipboardError("剪贴板声明有文本，但 GetClipboardData 失败，无法可靠备份。")
            pointer = kernel32.GlobalLock(handle)
            if not pointer:
                raise ClipboardError("剪贴板文本内存锁定失败，无法可靠备份。")
            try:
                text = ctypes.wstring_at(pointer)
            finally:
                kernel32.GlobalUnlock(handle)
            after = _sequence()
            if before != after:
                continue
            return {"status": "success", "text": text, "sequence": after}
        finally:
            _close()
    raise ClipboardError("剪贴板在读取备份期间持续变化，无法取得一致快照。")


def snapshot_text() -> dict[str, Any]:
    with _LOCK:
        return _snapshot_unlocked()


def get_text() -> str | None:
    """读取 Unicode 文本；没有文本格式时返回 None。"""
    snapshot = snapshot_text()
    return snapshot["text"] if snapshot["status"] == "success" else None


def _write_unlocked(text: str) -> int:
    data = (text + "\x00").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not handle:
        raise ClipboardError("GlobalAlloc 失败，无法分配剪贴板内存。")
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        raise ClipboardError("GlobalLock 失败，无法写入剪贴板内存。")
    try:
        ctypes.memmove(pointer, data, len(data))
    finally:
        kernel32.GlobalUnlock(handle)

    _open()
    try:
        if not user32.EmptyClipboard():
            raise ClipboardError("EmptyClipboard 失败。")
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            raise ClipboardError("SetClipboardData 失败。")
        # 成功后系统接管内存，不能再 GlobalFree。
        initial = _sequence()
    except Exception:
        kernel32.GlobalFree(handle)
        raise
    finally:
        _close()
    return _stable_sequence(initial)


def _empty_unlocked() -> int:
    _open()
    try:
        if not user32.EmptyClipboard():
            raise ClipboardError("EmptyClipboard 失败。")
        initial = _sequence()
    finally:
        _close()
    return _stable_sequence(initial)


def set_text(text: str, backup: bool = True) -> dict[str, Any]:
    """写入文本；backup=True 时必须先成功取得快照，备份失败不写。"""
    global _backup
    if not isinstance(text, str):
        raise ClipboardError("text 必须是字符串。")
    with _LOCK:
        snapshot = _snapshot_unlocked() if backup else None
        owned = _write_unlocked(text)
        if backup and snapshot is not None:
            _backup = {"snapshot": snapshot, "owned_sequence": owned, "at": time.time()}
        return {
            "written": len(text),
            "backup_saved": bool(backup),
            "backup_status": None if snapshot is None else snapshot["status"],
            "backup_had_text": bool(snapshot and snapshot["status"] == "success"),
            "sequence": owned,
        }


def clear(backup: bool = True) -> dict[str, Any]:
    global _backup
    with _LOCK:
        snapshot = _snapshot_unlocked() if backup else None
        owned = _empty_unlocked()
        if backup and snapshot is not None:
            _backup = {"snapshot": snapshot, "owned_sequence": owned, "at": time.time()}
        return {
            "cleared": True,
            "backup_saved": bool(backup),
            "backup_status": None if snapshot is None else snapshot["status"],
            "backup_had_text": bool(snapshot and snapshot["status"] == "success"),
            "sequence": owned,
        }


def restore() -> dict[str, Any]:
    """恢复最近一次 set/clear 前的文本；期间出现外部复制则冲突，不覆盖。"""
    global _backup
    with _LOCK:
        if _backup is None:
            return {
                "restored": False,
                "error_code": "no_backup",
                "message": "本会话没有可恢复的剪贴板快照。",
            }
        payload = _backup
        current = _sequence()
        if current != int(payload["owned_sequence"]):
            return {
                "restored": False,
                "conflict": True,
                "error_code": "clipboard_changed",
                "message": "剪贴板已被外部修改；为避免覆盖新内容，未恢复旧快照。",
                "expected_sequence": int(payload["owned_sequence"]),
                "current_sequence": current,
            }
        snapshot = payload["snapshot"]
        if snapshot["status"] == "success":
            owned = _write_unlocked(snapshot["text"])
            _backup = None
            return {
                "restored": True,
                "had_text": True,
                "restored_length": len(snapshot["text"]),
                "sequence": owned,
            }
        owned = _empty_unlocked()
        _backup = None
        return {"restored": True, "had_text": False, "restored_length": 0, "sequence": owned}
