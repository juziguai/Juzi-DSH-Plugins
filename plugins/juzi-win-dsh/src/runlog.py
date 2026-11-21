#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本次运行内的操作日志。

只写系统临时目录 `juzi-win-dsh-<pid>.jsonl`，进程正常退出时删除；
不落项目目录、不写注册表、不跨运行保留。日志线程安全，任何写入失败都
不会影响工具本身返回。
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class RunLog:
    def __init__(self) -> None:
        self.path = Path(tempfile.gettempdir()) / f"juzi-win-dsh-{os.getpid()}.jsonl"
        self._lock = threading.Lock()
        self._handle = None
        try:
            self._handle = open(self.path, "a", encoding="utf-8", buffering=1)
        except OSError:
            self._handle = None

    def write(
        self,
        tool: str,
        phase: str,
        params: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
        outcome: str | None = None,
        error: str | None = None,
    ) -> None:
        if self._handle is None:
            return
        record: dict[str, Any] = {
            "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "tool": tool,
            "phase": phase,
        }
        if params is not None:
            record["params"] = params
        if target is not None:
            record["target"] = {
                key: target.get(key)
                for key in ("hwnd", "process", "pid", "title", "minimized", "foreground")
            }
        if outcome is not None:
            record["outcome"] = outcome
        if error is not None:
            record["error"] = error
        line = json.dumps(record, ensure_ascii=False, default=str)
        try:
            with self._lock:
                self._handle.write(line + "\n")
        except (OSError, ValueError):
            pass

    def close(self) -> None:
        with self._lock:
            handle, self._handle = self._handle, None
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
