#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简 JSON Schema 校验（仅覆盖本插件工具 schema 用到的关键字）。

目的不是实现完整 JSON Schema，而是把 MCP 参数契约变成**派发前的强制校验**：
- boolean 只接受 JSON true/false；
- integer 只接受真正的 int（拒绝 bool/float/字符串）；
- number 拒绝 NaN/Infinity；
- 未知字段默认拒绝；
- 递归校验对象/数组/枚举/上下限/长度。
"""

from __future__ import annotations

import math
from typing import Any


def _type_matches(expected: str, value: Any) -> bool:
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "null":
        return value is None
    return False


def validate(schema: dict[str, Any], value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(item, value) for item in types):
            errors.append(f"{path}: 类型必须是 {'/'.join(types)}，实际是 {type(value).__name__}")
            return errors

    enum = schema.get("enum")
    if enum is not None and value not in enum:
        errors.append(f"{path}: 必须是 {enum} 之一")

    if isinstance(value, str):
        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(value) > max_length:
            errors.append(f"{path}: 长度不能超过 {max_length}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{path}: 不能小于 {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            errors.append(f"{path}: 不能大于 {maximum}")

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in value:
                errors.append(f"{path}: 缺少必填字段 {key}")
        additional = schema.get("additionalProperties", False)
        for key, item in value.items():
            if key in properties:
                errors.extend(validate(properties[key], item, f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}: 不接受未知字段 {key}")
            elif isinstance(additional, dict):
                errors.extend(validate(additional, item, f"{path}.{key}"))

    if isinstance(value, list) and schema.get("items"):
        for index, item in enumerate(value):
            errors.extend(validate(schema["items"], item, f"{path}[{index}]"))
    return errors
