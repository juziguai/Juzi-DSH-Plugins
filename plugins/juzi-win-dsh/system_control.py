#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用 system_control.ps1 完成亮度 / 音量 / 静音 / 锁屏。"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parent / "system_control.ps1"
POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def apply_system(request: dict[str, Any]) -> dict[str, Any]:
    """执行一次系统控制；返回 PowerShell 的 JSON 结果。"""
    command = [
        str(POWERSHELL),
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCRIPT),
        "-RequestJson",
        json.dumps(request, ensure_ascii=False),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=40,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stdout = (completed.stdout or "").strip().lstrip("\ufeff")
    if not stdout:
        raise RuntimeError(
            f"system_control.ps1 没有输出（exit={completed.returncode}）：{(completed.stderr or '').strip()[:500]}"
        )
    # PowerShell 可能先输出 CLIXML 警告；取最后一行 JSON。
    line = next((item for item in reversed(stdout.splitlines()) if item.strip().startswith("{")), "")
    if not line:
        raise RuntimeError(f"system_control.ps1 输出不是 JSON：{stdout[:500]}")
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"system_control.ps1 输出 JSON 解析失败：{exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("system_control.ps1 返回的 JSON 顶层不是对象。")
    return payload
