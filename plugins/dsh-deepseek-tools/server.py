#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Juzi-DeepSeek-Tools — DeepSeek 官方 Search / Fetch 的 MCP stdio 服务。

设计要点（给后续维护者）：
1. 只封装 DeepSeek 官方两个只读 HTTP 接口，不引入额外搜索源：
   - POST https://api.deepseek.com/v1/tools/search
   - POST https://api.deepseek.com/v1/tools/fetch
2. 只读取 DEEPSEEK_API_KEY：进程环境变量 -> 用户环境注册表 -> 系统环境注册表。
   末两级是为了适配会清洗 *KEY*/*TOKEN* 环境变量的宿主（如 DSH 的 MCP
   客户端：stdio 子进程环境会删除匹配 /KEY|PASSWORD|SECRET|TOKEN/i 的变量）。
3. stdout 是 MCP 协议通道，任何日志只能走 stderr；本文件不 print 到 stdout。
4. 工具 ID 直接使用品牌别名 DeepSeek-Search / DeepSeek-Fetch，完整调用名是
   mcp__deepseek__DeepSeek-Search / mcp__deepseek__DeepSeek-Fetch；
   权限规则统一用 mcp__deepseek__* 覆盖。
5. 计费口径与官方一致：HTTP 200 且 Search 的 results 非空 / Fetch 的 content
   非空，才计一次成功；失败、无结果、超时都不计费也不计数。
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from usage_store import record_success

VERSION = "1.1.1"

# 显式自定义网关必须可信且使用 HTTPS；不会跟随任何重定向。
BASE_URL = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_HTTP = urllib.request.build_opener(_NoRedirect())


def _endpoint(path: str) -> str:
    parsed = urllib.parse.urlsplit(BASE_URL)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or any(char.isspace() for char in BASE_URL)):
        raise ValueError("invalid API base")
    _ = parsed.port
    return f"{BASE_URL}{path}"


def _env_float(name: str, default: float) -> float:
    """读浮点环境变量；值非法时回退默认值而不是让服务起不来。"""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        print(f"[deepseek-tools] {name} 不是数字，回退默认值 {default:g}。", file=sys.stderr)
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int, minimum: int = 0, maximum: int = 10) -> int:
    """读整数环境变量并夹到 [minimum, maximum]，非法值回退默认。"""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        print(f"[deepseek-tools] {name} 不是整数，回退默认值 {default}。", file=sys.stderr)
        return default
    return max(minimum, min(maximum, value))


TIMEOUT_SECONDS = _env_float("DEEPSEEK_TOOLS_TIMEOUT", 60.0)
# 追加尝试次数：默认 1 次重试（最多 2 次请求），仅在 408/429/5xx 与超时上生效。
MAX_RETRIES = _env_int("DEEPSEEK_TOOLS_RETRIES", 1, minimum=0, maximum=3)
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 8.0

mcp = FastMCP("deepseek", log_level="WARNING")


def _windows_env(name: str) -> str:
    """从 Windows 用户级 / 系统级环境注册表读取变量；非 Windows 返回空串。"""
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return ""

    for root, path in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(root, path) as handle:
                value, _ = winreg.QueryValueEx(handle, name)
        except OSError:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


@lru_cache(maxsize=1)
def _api_key_cached() -> str:
    """按优先级解析一次并缓存；环境变量优先，注册表兜底。"""
    return os.environ.get("DEEPSEEK_API_KEY", "").strip() or _windows_env("DEEPSEEK_API_KEY")


def _api_key() -> str:
    """读取 DeepSeek Key；不存在时返回空串，由调用方转成可读错误。"""
    return _api_key_cached()


def _dump(payload: dict[str, Any]) -> str:
    """统一输出 JSON 文本；ensure_ascii=False 保留中文，减少 token 浪费。"""
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _record_usage(tool: str) -> None:
    """成功计数是旁路能力，任何异常都不能影响搜索结果返回。"""
    try:
        record_success(tool)
    except Exception as exc:  # usage_store 内部已兜底，这里再保一层
        print(f"[deepseek-tools] usage record failed: {exc}", file=sys.stderr)


def _as_int(value: Any, default: int) -> int:
    """把 MCP 传来的值转成 int；转不动就返回默认值（不抛异常）。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _retry_delay(exc: urllib.error.HTTPError | None, attempt: int) -> float:
    """优先遵守 Retry-After，否则用 0.5s 起的指数退避。"""
    if exc is not None:
        header = exc.headers.get("Retry-After") if exc.headers else None
        if header:
            try:
                return min(MAX_BACKOFF_SECONDS, max(0.0, float(header)))
            except (TypeError, ValueError):
                pass
    return min(MAX_BACKOFF_SECONDS, 0.5 * (2**attempt))


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """调用 DeepSeek 官方接口，并把网络/HTTP 错误转成结构化 JSON。

    注意：错误不抛异常，而是作为工具结果返回，方便模型看到 400/429 等
    具体原因并决定是否重试；只有 Key 缺失属于配置问题，也返回结构化错误。
    408/429/5xx 与超时按 MAX_RETRIES 自动重试，其余错误立即返回。
    """
    try:
        endpoint = _endpoint(path)
    except ValueError:
        return {"error": "invalid_api_base", "message": "API 地址必须使用 HTTPS，且不能包含凭证、查询参数或片段。"}
    key = _api_key()
    if not key:
        return {
            "error": "missing_api_key",
            "message": (
                "未找到 DEEPSEEK_API_KEY（环境变量与 Windows "
                "环境注册表均已检查），无法调用 DeepSeek 官方工具接口。"
            ),
        }
    if not key.isascii() or any(ord(char) <= 32 or ord(char) == 127 for char in key):
        return {"error": "invalid_api_key", "message": "专用 API Key 格式无效，请检查环境变量设置。"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    attempts = MAX_RETRIES + 1
    last: dict[str, Any] | None = None

    for attempt in range(attempts):
        retry_exc: urllib.error.HTTPError | None = None
        request = urllib.request.Request(
            url=endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"Juzi-DeepSeek-Tools/{VERSION}",
            },
        )
        try:
            with _HTTP.open(request, timeout=TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8", errors="replace")
            if not raw:
                return {"error": "empty_response", "message": "DeepSeek 返回了空响应体。"}
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                return {"error": "invalid_json", "message": f"响应不是合法 JSON: {exc}"}
            if not isinstance(parsed, dict):
                return {
                    "error": "invalid_response",
                    "message": f"响应顶层不是 JSON 对象，而是 {type(parsed).__name__}。",
                }
            if key in json.dumps(parsed, ensure_ascii=False):
                return {"error": "unsafe_response", "message": "接口响应包含鉴权信息，已阻止返回。"}
            return parsed

        except urllib.error.HTTPError as exc:
            # Upstream errors and Location headers are untrusted and can echo credentials.
            exc.close()
            result = {
                "error": "redirect_blocked" if 300 <= exc.code < 400 else "http_error",
                "status": exc.code,
                "message": "接口拒绝请求或返回重定向；响应体和响应头未转发。",
                "hint": "408/429/5xx 可等待后重试；402 需充值；403 为安全策略拒绝（换 URL）；其它 4xx 不改请求不要重试。",
            }
            if exc.code not in RETRYABLE_STATUS or attempt == attempts - 1:
                return result
            retry_exc = exc
            last = result

        except TimeoutError:
            result = {"error": "timeout", "message": f"请求超过 {TIMEOUT_SECONDS:g} 秒。"}
            if attempt == attempts - 1:
                return result
            last = result

        except urllib.error.URLError as exc:
            # 连接超时在部分平台表现为 URLError(socket.timeout)，同样可重试。
            if isinstance(exc.reason, TimeoutError):
                result = {"error": "timeout", "message": f"请求超过 {TIMEOUT_SECONDS:g} 秒。"}
            else:
                result = {"error": "network_error", "message": "无法连接接口，请检查网络、代理与 TLS 配置。"}
            if not isinstance(exc.reason, TimeoutError) or attempt == attempts - 1:
                return result
            last = result

        delay = _retry_delay(retry_exc, attempt)
        print(
            f"[deepseek-tools] {path} 第 {attempt + 1}/{attempts} 次失败，{delay:.2f}s 后重试。",
            file=sys.stderr,
        )
        time.sleep(delay)

    return last or {"error": "unknown", "message": "请求未产生结果。"}


@mcp.tool(
    name="DeepSeek-Search",
    title="DeepSeek-Search",
    description=(
        "DeepSeek-Search：调用 DeepSeek 官方搜索接口，返回带标题、URL、摘要、"
        "发布时间、权威性和重排分数的结构化结果。支持 site:、-site:、引号等语法。"
    ),
)
def search(
    query: str,
    count: int = 10,
    need_content: bool = False,
    ori_question: str | None = None,
    localization: str = "",
    max_content_chars: int = 8000,
) -> str:
    """搜索实时网页。

    Args:
        query: 搜索词，1~128 个 Unicode 字符，不能全为空白。
        count: 返回条数，1~50，默认 10；条数不影响单次计费。
        need_content: 是否在每条结果里返回网页正文；默认 False 节省上下文。
        ori_question: 触发搜索的用户原始问题（1~128 字符），帮助理解搜索意图。
        localization: 用于优先本地化结果的 IP 地址，默认空字符串。
        max_content_chars: need_content=True 时每条正文最多保留多少字符，
            0 表示不截断；默认 8000，避免一次搜索撑爆上下文。
    """
    query = (query or "").strip() if isinstance(query, str) else ""
    if not query:
        return _dump({"error": "invalid_query", "message": "query 不能为空。"})
    if len(query) > 128:
        return _dump({"error": "invalid_query", "message": "query 不能超过 128 个 Unicode 字符。"})

    count_value = _as_int(count, -1)
    if not 1 <= count_value <= 50:
        return _dump({"error": "invalid_count", "message": "count 必须是 1 到 50 之间的整数。"})

    if ori_question is not None:
        if not isinstance(ori_question, str):
            return _dump({"error": "invalid_ori_question", "message": "ori_question 必须是字符串。"})
        ori_question = ori_question.strip()
        if not ori_question:
            ori_question = None
        elif len(ori_question) > 128:
            return _dump({"error": "invalid_ori_question", "message": "ori_question 不能超过 128 个字符。"})

    limit = _as_int(max_content_chars, 8000)

    payload: dict[str, Any] = {
        "query": query,
        "count": count_value,
        "need_content": bool(need_content),
        "localization": localization if isinstance(localization, str) else "",
    }
    if ori_question:
        payload["ori_question"] = ori_question

    result = _post("/v1/tools/search", payload)
    if "error" in result:
        return _dump(result)

    results = result.get("results")
    if not isinstance(results, list):
        results = []
    results = [item for item in results if isinstance(item, dict)]

    # 计费口径：HTTP 200 且 results 非空才算一次成功搜索。
    if results:
        _record_usage("search")
    if need_content and limit > 0:
        for item in results:
            content = item.get("content") or ""
            if isinstance(content, str) and len(content) > limit:
                item["content"] = content[:limit]
                item["content_truncated"] = True
                item["content_original_chars"] = len(content)

    return _dump({"source": "deepseek", "query": query, "count": len(results), "results": results})


@mcp.tool(
    name="DeepSeek-Fetch",
    title="DeepSeek-Fetch",
    description=(
        "DeepSeek-Fetch：调用 DeepSeek 官方抓取接口，把单个网页转换成 Markdown 正文。"
        "适合读取文档、文章、公告等页面内容。"
    ),
)
def fetch(url: str, max_chars: int = 30000) -> str:
    """抓取网页并返回 Markdown。

    Args:
        url: 要抓取的 HTTP/HTTPS 地址，长度不超过 8192，不能携带用户名或密码。
        max_chars: 最多保留多少字符，0 表示不截断；默认 30000。
    """
    url = (url or "").strip() if isinstance(url, str) else ""
    if not url:
        return _dump({"error": "invalid_url", "message": "url 不能为空。"})
    if len(url) > 8192:
        return _dump({"error": "invalid_url", "message": "url 不能超过 8192 个字符。"})
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return _dump({"error": "invalid_url", "message": "url 必须是含 host 的 HTTP/HTTPS 地址。"})
    if parsed.username or parsed.password:
        return _dump({"error": "invalid_url", "message": "url 不能携带用户名或密码。"})

    limit = _as_int(max_chars, 30000)

    result = _post("/v1/tools/fetch", {"url": url})
    if "error" in result:
        return _dump(result)

    content = result.get("content")
    content = content if isinstance(content, str) else ""
    # 计费口径：Fetch 必须真正返回网页正文才算成功。
    if content.strip():
        _record_usage("fetch")
    original_chars = len(content)
    truncated = False
    if limit > 0 and original_chars > limit:
        content = content[:limit]
        truncated = True

    title = result.get("title")
    return _dump(
        {
            "source": "deepseek",
            "url": url,
            "title": title if isinstance(title, str) else "",
            "content": content,
            "content_chars": original_chars,
            "truncated": truncated,
        }
    )


if __name__ == "__main__":
    # FastMCP 默认 stdio；不要在这里 print，stdout 被协议占用。
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
