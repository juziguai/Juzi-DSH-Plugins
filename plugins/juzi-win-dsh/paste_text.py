#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用剪贴板粘贴文本；文本走 stdin（不占 Windows 命令行），并恢复原剪贴板。"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).resolve().parent / "paste_text.ps1"
POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"


def paste_text(text: str, expected_hwnd: int | None = None, expected_focus: str = "") -> dict[str, Any]:
    command = [
        str(POWERSHELL),
        "-NoProfile",
        "-STA",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCRIPT),
        "-ExpectedHwnd",
        str(int(expected_hwnd or 0)),
        "-ExpectedFocus", expected_focus,
    ]
    completed = subprocess.run(
        command,
        input=text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stdout = (completed.stdout or "").strip().lstrip("\ufeff")
    line = next((item for item in reversed(stdout.splitlines()) if item.strip().startswith("{")), "")
    if not line:
        raise RuntimeError(
            f"paste_text.ps1 没有输出 JSON（exit={completed.returncode}）：{(completed.stderr or '').strip()[:500]}"
        )
    payload = json.loads(line)
    return payload
