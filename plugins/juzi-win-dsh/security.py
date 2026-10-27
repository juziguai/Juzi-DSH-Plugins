#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""禁止操作窗口清单与身份缺失拒绝。

安全边界覆盖：UAC 提权弹窗、Windows 安全中心、锁屏/登录界面、常见密码管理器。
匹配同时看进程名和标题；无法读取进程身份时按 fail-closed 拒绝写操作。
"""

from __future__ import annotations

from typing import Any

FORBIDDEN_PROCESSES = {
    # UAC / 登录 / 锁屏
    "consent.exe",
    "logonui.exe",
    "lockapp.exe",
    "credentialuibroker.exe",
    # Windows 安全中心 / Defender
    "sechealthui.exe",
    "securityhealthsystray.exe",
    "securityhealthhost.exe",
    "securityhealthservice.exe",
    "msmpeng.exe",
    # 常见密码管理器
    "1password.exe",
    "1passwordtray.exe",
    "bitwarden.exe",
    "keepass.exe",
    "keepassxc.exe",
    "lastpass.exe",
    "dashlane.exe",
    "keeper.exe",
    "keeperpasswordmanager.exe",
    "nordpass.exe",
    "roboform.exe",
    "passwordkeep.exe",
    "protonpass.exe",
    "enpass.exe",
}

FORBIDDEN_TITLE_PARTS = (
    "用户账户控制",
    "user account control",
    "windows 安全中心",
    "windows security",
    "密码管理器",
    "password manager",
    "密码管理工具",
    "密码 —",
    "密码 -",
    "saved passwords",
    "saved logins",
    "1password",
    "keepass",
    "bitwarden",
    "lastpass",
    "dashlane",
    "proton pass",
    "enpass",
)


def forbidden_reason(info: dict[str, Any] | None) -> str | None:
    """命中禁止清单时返回可读原因，否则返回 None。"""
    if not info:
        return None
    process = str(info.get("process") or "").strip().lower()
    title = str(info.get("title") or "").strip().casefold()
    if not process:
        return "拒绝操作：无法确认目标窗口进程身份（fail-closed）。"
    if process in FORBIDDEN_PROCESSES:
        return f"禁止操作受保护窗口：进程 {process}。"
    for part in FORBIDDEN_TITLE_PARTS:
        if part.casefold() in title:
            return f"禁止操作受保护窗口：标题包含「{part}」。"
    return None


def forbidden_windows(rect: dict[str, int]) -> list[dict[str, Any]]:
    """返回与给定屏幕矩形相交的可见禁止窗口；供 screenshot/find_text 区域检查。"""
    import winapi

    hits = []
    for item in winapi.list_windows(include_tool_windows=True):
        if forbidden_reason(item) and winapi.rects_intersect(item["rect"], rect):
            hits.append(
                {
                    "hwnd": item["hwnd"],
                    "process": item["process"],
                    "title": item["title"],
                    "rect": item["rect"],
                }
            )
    return hits
