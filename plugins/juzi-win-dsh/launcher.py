#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动应用：ShellExecuteExW（不经 cmd 拼接），并等待新窗口出现。"""

from __future__ import annotations

import ctypes
import os
import re
import time
from ctypes import wintypes as w
from typing import Any

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NOASYNC = 0x00000100
SW_SHOWNORMAL = 1
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# 脚本宿主、提权/注册表工具与常见卸载器：本批一律拒绝（README 已写明）。
BLOCKED_PROCESSES = {
    "consent.exe",
    "powershell.exe",
    "pwsh.exe",
    "cmd.exe",
    "wscript.exe",
    "cscript.exe",
    "mshta.exe",
    "reg.exe",
    "regedit.exe",
    "rundll32.exe",
    "msiexec.exe",
}
BLOCKED_EXTENSIONS = {
    ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".wsh", ".hta", ".reg", ".lnk", ".url",
}
UNINSTALLER_PATTERN = re.compile(r"^(unins|uninstall|unwise|setup.*uninstall)", re.IGNORECASE)
URI_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", w.DWORD),
        ("fMask", w.ULONG),
        ("hwnd", w.HWND),
        ("lpVerb", w.LPCWSTR),
        ("lpFile", w.LPCWSTR),
        ("lpParameters", w.LPCWSTR),
        ("lpDirectory", w.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", w.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", w.LPCWSTR),
        ("hkeyClass", w.HKEY),
        ("dwHotKey", w.DWORD),
        ("hIcon", w.HANDLE),
        ("hProcess", w.HANDLE),
    ]


shell32.ShellExecuteExW.restype = w.BOOL
shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
kernel32.GetProcessId.restype = w.DWORD
kernel32.GetProcessId.argtypes = [w.HANDLE]
kernel32.CloseHandle.restype = w.BOOL
kernel32.CloseHandle.argtypes = [w.HANDLE]


def _normalize(name: str) -> str:
    """Windows 会忽略文件名尾部的点和空格；按规范化名比较黑名单。"""
    name = os.path.basename((name or "").strip()).rstrip(" .").lower()
    return name[:-4] if name.endswith(".exe") else name


def _validate_path(path: str) -> dict[str, Any]:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path 必须是非空字符串。")
    path = path.strip()
    is_absolute = os.path.isabs(path)
    if re.match(r"^[A-Za-z]:", path) and not is_absolute:
        raise ValueError("path 必须是绝对路径或明确的 URI scheme（如 ms-settings:、shell:）。")
    is_uri = bool(URI_PATTERN.match(path)) and not is_absolute
    if not is_absolute and not is_uri:
        raise ValueError("path 必须是绝对路径或明确的 URI scheme（如 ms-settings:、shell:）。")
    if is_uri:
        return {"path": path, "uri": True, "kind": "uri", "name": ""}
    if not os.path.exists(path):
        raise ValueError(f"路径不存在：{path}")

    candidates = [path]
    try:
        resolved = os.path.realpath(path)
        if resolved and resolved != path:
            candidates.append(resolved)
    except OSError:
        pass

    blocked_names = {os.path.splitext(item)[0].lower() for item in BLOCKED_PROCESSES}
    for candidate in candidates:
        base = os.path.basename(candidate).rstrip(" .")
        stem, extension = os.path.splitext(base)
        name = stem.lower()
        extension = extension.lower()
        if name in blocked_names:
            raise PermissionError(f"本批拒绝启动脚本宿主、提权工具或卸载器：{name}.exe")
        if extension in BLOCKED_EXTENSIONS:
            raise PermissionError(f"本批拒绝启动脚本/快捷方式文件：{extension}")
        if UNINSTALLER_PATTERN.match(name):
            raise PermissionError(f"本批拒绝启动疑似卸载器：{base}")
    return {"path": path, "uri": False, "kind": "file", "name": _normalize(path)}


def launch(
    path: str,
    args: str | None = None,
    workdir: str | None = None,
    wait_window_ms: int = 5000,
) -> dict[str, Any]:
    import winapi

    validation = _validate_path(path)
    if workdir is not None:
        if not isinstance(workdir, str) or not os.path.isdir(workdir):
            raise ValueError(f"workdir 不是已存在的目录：{workdir}")

    before = {item["hwnd"] for item in winapi.list_windows()}
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(SHELLEXECUTEINFOW)
    info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    info.lpVerb = "open"
    info.lpFile = validation["path"]
    info.lpParameters = args or None
    info.lpDirectory = workdir or None
    info.nShow = SW_SHOWNORMAL

    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        code = ctypes.get_last_error()
        raise OSError(code, f"ShellExecuteExW 失败（WinError {code}）。")

    pid = int(kernel32.GetProcessId(info.hProcess)) if info.hProcess else 0
    process_name = ""
    if pid:
        process_name = winapi._process_name(pid)  # 与窗口枚举使用同一实现
    handle = info.hProcess

    deadline = time.monotonic() + max(0, int(wait_window_ms)) / 1000.0
    found = None
    try:
        while int(wait_window_ms) > 0 and time.monotonic() < deadline:
            for item in winapi.list_windows():
                if item["hwnd"] in before:
                    continue
                if pid and item["pid"] == pid:
                    found = item
                    break
                if process_name and item["process"].lower() == process_name.lower():
                    found = item
                    break
            if found:
                break
            time.sleep(0.1)
    finally:
        if handle:
            kernel32.CloseHandle(handle)

    return {
        "started": True,
        "path": validation["path"],
        "kind": validation["kind"],
        "pid": pid or None,
        "process": process_name or None,
        "window": found,
        "waited_ms": int(wait_window_ms),
    }
