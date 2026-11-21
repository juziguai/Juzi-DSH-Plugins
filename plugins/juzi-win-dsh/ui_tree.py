#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows UI Automation 控件树常驻 STA 采集器。

通过常驻 PowerShell + 编译 C# CacheRequest BFS，毫秒级读取任意可见窗口的
交互控件与文本（Name、类型、屏幕物理像素中心坐标、enabled/selected/checked/expanded），
让 AI 免截图、免 OCR 猜坐标就能看清界面与置灰状态。
"""

from __future__ import annotations

import atexit
import json
import queue
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from paste_text import POWERSHELL

SCRIPT_PATH = Path(__file__).resolve().with_suffix(".ps1")
MAX_UI_RESPONSE_BYTES = 16 * 1024 * 1024


class UiTreeWorker:
    """常驻 STA UIA Worker：首次启动编译 C#，后续复用避免冷启动开销。"""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.responses: queue.Queue[Any] | None = None

    def _start(self) -> None:
        process = subprocess.Popen(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-STA",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=tempfile.gettempdir(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        responses: queue.Queue[Any] = queue.Queue()
        self.process, self.responses = process, responses

        def receive() -> None:
            assert process.stdout is not None
            try:
                while True:
                    line = process.stdout.readline(MAX_UI_RESPONSE_BYTES + 1)
                    if not line:
                        raise RuntimeError("UI Automation tree worker exited")
                    if len(line) > MAX_UI_RESPONSE_BYTES:
                        raise RuntimeError("UI Automation tree response exceeds limit")
                    stripped = line.lstrip("\ufeff").strip()
                    if not stripped:
                        continue
                    responses.put(json.loads(stripped))
            except Exception as exc:  # noqa: BLE001
                responses.put(exc)
            finally:
                try:
                    process.stdout.close()
                except OSError:
                    pass

        threading.Thread(target=receive, name="juzi-ui-tree-worker", daemon=True).start()

    def _close(self) -> None:
        process, self.process = self.process, None
        self.responses = None
        if process is None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass

    def close(self) -> None:
        with self.lock:
            self._close()

    def inspect(
        self,
        hwnd: int | None = None,
        max_elements: int = 150,
        max_depth: int = 12,
        interactive_only: bool = False,
        include_text: bool = True,
        skip_offscreen: bool = True,
        query: str | None = None,
        timeout_ms: int = 2500,
        region: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "hwnd": hwnd,
            "max_elements": int(max_elements),
            "max_depth": int(max_depth),
            "interactive_only": bool(interactive_only),
            "include_text": bool(include_text),
            "skip_offscreen": bool(skip_offscreen),
            "query": query or "",
            "timeout_ms": int(timeout_ms),
            "region": region,
        }
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None:
                    self._close()
                    self._start()
                assert self.process is not None and self.process.stdin is not None and self.responses is not None
                self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
                wait_timeout = max(self.timeout, timeout_ms / 1000.0 + 10.0)
                response = self.responses.get(timeout=wait_timeout)
                if isinstance(response, Exception):
                    raise response
                if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
                    raise RuntimeError("Invalid UI Automation tree worker response")
                return response
            except queue.Empty as exc:
                self._close()
                raise TimeoutError("UI Automation tree worker timed out") from exc
            except Exception:
                self._close()
                raise


_worker = UiTreeWorker()
close = _worker.close
atexit.register(close)


def inspect(
    hwnd: int | None = None,
    max_elements: int = 150,
    max_depth: int = 12,
    interactive_only: bool = False,
    include_text: bool = True,
    skip_offscreen: bool = True,
    query: str | None = None,
    timeout_ms: int = 2500,
    region: dict[str, int] | None = None,
) -> dict[str, Any]:
    if not SCRIPT_PATH.exists():
        return {"ok": False, "error": "uia_unavailable", "message": "缺少 ui_tree.ps1。"}
    return _worker.inspect(
        hwnd=hwnd,
        max_elements=max_elements,
        max_depth=max_depth,
        interactive_only=interactive_only,
        include_text=include_text,
        skip_offscreen=skip_offscreen,
        query=query,
        timeout_ms=timeout_ms,
        region=region,
    )
