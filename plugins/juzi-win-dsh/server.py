#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「电脑控制」MCP stdio 稳定公共入口（兼容 DSH 插件与外部 MCP 客户端）。"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_DIR = str(Path(__file__).resolve().parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import core_server as _core  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_core.main())
else:
    sys.modules[__name__] = _core
