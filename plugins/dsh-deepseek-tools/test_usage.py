#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""usage_store.py 的计数/并发/持久化测试。

覆盖：
1. 成功计数 +1，失败工具名不计数；
2. 8 个进程 × 20 次并发递增，总数不丢（锁 + 原子替换）；
3. 进程结束后重新读取仍能拿到总数（持久化）；
4. 不残留临时文件或锁文件。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL_DIR = str(Path(__file__).resolve().parent)
PYTHON = sys.executable

WORKER = r"""
import os, sys
os.environ["DEEPSEEK_USAGE_PATH"] = sys.argv[1]
sys.path.insert(0, sys.argv[2])
import usage_store
for _ in range(int(sys.argv[3])):
    if not usage_store.record_success(sys.argv[4]):
        raise SystemExit(2)
"""


def main() -> int:
    temp_dir = tempfile.mkdtemp(prefix="deepseek-usage-test-")
    usage_path = os.path.join(temp_dir, "usage.json")
    os.environ["DEEPSEEK_USAGE_PATH"] = usage_path

    try:
        # 让本进程导入的是同一个 usage_store 模块。
        sys.path.insert(0, TOOL_DIR)
        import usage_store

        # 1) 基础递增 + 失败工具名
        assert usage_store.read_usage()["search"]["success"] == 0
        assert usage_store.record_success("search") is True
        assert usage_store.record_success("search") is True
        assert usage_store.record_success("fetch") is True
        assert usage_store.record_success("bogus") is False
        base = usage_store.read_usage()
        assert base["search"]["success"] == 2, base
        assert base["fetch"]["success"] == 1, base
        print("SIMPLE_OK", json.dumps(base, ensure_ascii=False))

        # 2) 并发递增：删除旧文件，8 进程 × 20 次
        Path(usage_path).unlink(missing_ok=True)
        Path(usage_path + ".lock").unlink(missing_ok=True)

        process_count = 8
        per_process = 20
        processes = [
            subprocess.Popen(
                [PYTHON, "-c", WORKER, usage_path, TOOL_DIR, str(per_process), "search"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(process_count)
        ]
        for process in processes:
            stdout, stderr = process.communicate(timeout=120)
            assert process.returncode == 0, (process.returncode, stdout, stderr)

        concurrent = usage_store.read_usage()
        expected = process_count * per_process
        assert concurrent["search"]["success"] == expected, concurrent
        assert concurrent["fetch"]["success"] == 0, concurrent
        print("CONCURRENCY_OK", json.dumps(concurrent, ensure_ascii=False))

        # 3) 持久化：重新读取同一路径
        again = usage_store.read_usage()
        assert again["search"]["success"] == expected, again

        # 4) 不残留临时文件/锁文件
        leftovers = [
            path.name
            for path in Path(temp_dir).iterdir()
            if path.name.endswith(".tmp") or path.name.endswith(".lock")
        ]
        assert leftovers == [], leftovers
        print("CLEANUP_OK")

        print("ALL_TESTS_PASSED")
        return 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
