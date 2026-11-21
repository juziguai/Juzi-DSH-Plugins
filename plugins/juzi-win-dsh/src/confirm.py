#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""confirm_mode 的一次性确认令牌。

MCP 服务无法直接弹 DSH 的确认框，因此采用两阶段协议：
1. 第一次调用只返回 confirmation_required + confirm_token，绝不执行；
2. 模型必须先在 dsh 里向用户确认，再用同一个 token 重试。
令牌绑定 action + 参数 + 目标窗口，单次有效，180 秒过期。
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

TOKEN_TTL_SECONDS = 180
MAX_PENDING = 64


def _normalize_process(value: str) -> str:
    name = (value or "").strip().lower()
    return name[:-4] if name.endswith(".exe") else name


def _digest(action: str, params: dict[str, Any], target: dict[str, Any] | None) -> str:
    payload = {
        "action": action,
        "params": params,
        "target": {
            "hwnd": int((target or {}).get("hwnd") or 0),
            "process": _normalize_process(str((target or {}).get("process") or "")),
            "title": str((target or {}).get("title") or ""),
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class Pending:
    action: str
    digest: str
    expires_at: float


class ConfirmationGate:
    def __init__(self, mode: str, allowlist: list[str]) -> None:
        self.mode = mode if mode in ("always", "allowlist", "off") else "always"
        self.allowlist = {_normalize_process(item) for item in allowlist if item.strip()}
        self._pending: dict[str, Pending] = {}

    def needs_confirmation(self, target: dict[str, Any] | None) -> bool:
        if self.mode == "off":
            return False
        if self.mode == "allowlist":
            process = _normalize_process(str((target or {}).get("process") or ""))
            if process and process in self.allowlist:
                return False
        return True

    def issue(self, action: str, params: dict[str, Any], target: dict[str, Any] | None) -> dict[str, Any]:
        self._prune()
        token = secrets.token_urlsafe(18)
        self._pending[token] = Pending(
            action=action,
            digest=_digest(action, params, target),
            expires_at=time.time() + TOKEN_TTL_SECONDS,
        )
        # 只保留最近 MAX_PENDING 个未使用令牌，避免内存无限增长。
        while len(self._pending) > MAX_PENDING:
            oldest = next(iter(self._pending))
            self._pending.pop(oldest, None)
        return {"confirm_token": token, "expires_in": TOKEN_TTL_SECONDS}

    def verify(
        self,
        action: str,
        params: dict[str, Any],
        target: dict[str, Any] | None,
        token: str,
    ) -> tuple[bool, str]:
        self._prune()
        pending = self._pending.get(token)
        if pending is None:
            return False, "确认令牌不存在或已过期。"
        if pending.action != action or pending.digest != _digest(action, params, target):
            return False, "确认令牌与本次操作参数或目标窗口不匹配。"
        self._pending.pop(token, None)
        return True, ""

    def _prune(self) -> None:
        now = time.time()
        expired = [token for token, pending in self._pending.items() if pending.expires_at <= now]
        for token in expired:
            self._pending.pop(token, None)
