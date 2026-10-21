#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DeepSeek-Search / DeepSeek-Fetch 成功次数持久化。

设计约束（对应需求）：
1. 只有真正成功的请求才调用 record_success()；失败/超时/取消由 server.py
   在调用前拦截，根本不会走到这里。
2. 计数文件是多进程共享的，因此用“锁文件 + 临时文件 + os.replace”实现
   原子读改写；即使两个 Claude Code 会话同时命中，也不会丢计数。
3. 锁文件带超时与陈旧锁清理，避免上一次进程崩溃后永久卡死。
4. 文件路径默认与 HUD 约定一致：<CLAUDE_CONFIG_DIR 或 ~/.claude>/
   deepseek-tools-usage.json；测试可用 DEEPSEEK_USAGE_PATH 覆盖。

文件格式：
{
  "version": 1,
  "search": {"success": 123, "last_success_at": "2026-10-17T..."},
  "fetch":  {"success": 45,  "last_success_at": "2026-10-17T..."},
  "updated_at": "2026-10-17T..."
}
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOLS = ("search", "fetch")
LOCK_TIMEOUT_SECONDS = 5.0
STALE_LOCK_SECONDS = 15.0


def usage_path() -> Path:
    """返回计数文件路径；HUD 侧使用同一套解析规则。"""
    override = os.environ.get("DEEPSEEK_USAGE_PATH", "").strip()
    if override:
        return Path(override).expanduser()

    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    base = Path(config_dir).expanduser() if config_dir else Path.home() / ".claude"
    return base / "deepseek-tools-usage.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _empty() -> dict[str, Any]:
    return {
        "version": 1,
        "search": {"success": 0, "last_success_at": None},
        "fetch": {"success": 0, "last_success_at": None},
        "updated_at": None,
    }


def _normalize(raw: Any) -> dict[str, Any]:
    """容忍旧版本/手工编辑：只接受非负数字，其余字段回到默认值。"""
    data = _empty()
    if not isinstance(raw, dict):
        return data

    for tool in TOOLS:
        section = raw.get(tool)
        if not isinstance(section, dict):
            continue
        value = section.get("success")
        if isinstance(value, bool):
            value = None
        if isinstance(value, (int, float)) and value >= 0:
            data[tool]["success"] = int(value)
        last = section.get("last_success_at")
        if isinstance(last, str) and last:
            data[tool]["last_success_at"] = last

    updated = raw.get("updated_at")
    if isinstance(updated, str) and updated:
        data["updated_at"] = updated
    return data


def read_usage(path: Path | None = None) -> dict[str, Any]:
    """读取计数；文件不存在或损坏时返回全 0 结构，方便 HUD/测试调用。"""
    target = path or usage_path()
    try:
        with open(target, "r", encoding="utf-8") as handle:
            return _normalize(json.load(handle))
    except FileNotFoundError:
        return _empty()
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[deepseek-tools] 无法读取用量文件 {target}: {exc}", file=sys.stderr)
        return _empty()


def _load_for_update(path: Path) -> dict[str, Any]:
    """加锁后的读取；损坏文件先改名备份，再以全 0 重新开始。"""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return _normalize(json.load(handle))
    except FileNotFoundError:
        return _empty()
    except (json.JSONDecodeError, OSError) as exc:
        backup = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        try:
            os.replace(path, backup)
            print(f"[deepseek-tools] 用量文件损坏，已备份到 {backup}", file=sys.stderr)
        except OSError:
            print(f"[deepseek-tools] 用量文件损坏且无法备份 {path}: {exc}", file=sys.stderr)
        return _empty()


def _acquire_lock(lock_path: Path) -> bool:
    """O_CREAT|O_EXCL 创建锁文件；Windows 上同样是原子创建。"""
    started = time.monotonic()
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}".encode("ascii"))
            os.close(fd)
            return True
        except FileExistsError:
            # 上一次进程崩溃可能留下锁；超过阈值视为陈旧锁。
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > STALE_LOCK_SECONDS:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            except OSError:
                pass
            if time.monotonic() - started >= LOCK_TIMEOUT_SECONDS:
                return False
            time.sleep(0.02)
        except OSError as exc:
            print(f"[deepseek-tools] 无法创建锁文件 {lock_path}: {exc}", file=sys.stderr)
            return False


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """同目录临时文件 + os.replace，保证读者永远看到完整 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def record_success(tool: str) -> bool:
    """成功计数 +1；返回是否写入成功。失败不影响调用方的主流程。"""
    if tool not in TOOLS:
        return False

    target = usage_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[deepseek-tools] 无法创建用量目录 {target.parent}: {exc}", file=sys.stderr)
        return False

    lock_path = target.with_name(f"{target.name}.lock")
    acquired = False
    try:
        acquired = _acquire_lock(lock_path)
        if not acquired:
            print("[deepseek-tools] 用量计数锁超时，本次计数跳过。", file=sys.stderr)
            return False

        data = _load_for_update(target)
        data[tool]["success"] += 1
        data[tool]["last_success_at"] = _now_iso()
        data["updated_at"] = _now_iso()
        _atomic_write(target, data)
        return True
    except Exception as exc:  # 计数失败不能拖垮搜索/抓取本身
        print(f"[deepseek-tools] 用量计数失败: {exc}", file=sys.stderr)
        return False
    finally:
        if acquired:
            try:
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    print(json.dumps(read_usage(), ensure_ascii=False, indent=2))
