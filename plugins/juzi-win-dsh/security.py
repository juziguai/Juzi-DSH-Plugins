#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""禁止操作窗口清单。

安全边界只覆盖最容易造成不可逆后果的系统界面与密码管理器：
UAC 提权弹窗、Windows 安全中心、锁屏/登录界面、常见密码管理器。
匹配同时看进程名和标题，避免只改标题或只改进程名就绕过。
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
    "nordpass.exe",
    "roboform.exe",
    "passwordkeep.exe",
}

FORBIDDEN_TITLE_PARTS = (
    "用户账户控制",
    "user account control",
    "windows 安全中心",
    "windows security",
    "密码管理器",
    "password manager",
    "1password",
    "keepass",
    "bitwarden",
    "lastpass",
    "dashlane",
)


def forbidden_reason(info: dict[str, Any] | None) -> str | None:
    """命中禁止清单时返回可读原因，否则返回 None。"""
    if not info:
        return None
    process = str(info.get("process") or "").strip().lower()
    title = str(info.get("title") or "").strip().casefold()
    if process in FORBIDDEN_PROCESSES:
        return f"禁止操作受保护窗口：进程 {process}。"
    for part in FORBIDDEN_TITLE_PARTS:
        if part.casefold() in title:
            return f"禁止操作受保护窗口：标题包含「{part}」。"
    return None
