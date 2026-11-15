#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Juzi-DeepSeek-Tools — DeepSeek 官方 Search / Fetch 的 MCP stdio 服务（含 WorkBuddy 网关搜索扩容与自动降级）。

设计要点（给后续维护者）：
1. 主通道封装 DeepSeek 官方两个只读 HTTP 接口：
   - POST https://api.deepseek.com/v1/tools/search
   - POST https://api.deepseek.com/v1/tools/fetch
2. 搜索扩容与自动降级（Fallback）：
   - 默认（provider="auto"）优先调用 DeepSeek 官方搜索接口；
   - 当 DeepSeek 官方搜索不可用（如未配置 Key、402 余额不足、429 限流、5xx 故障、网络超时）
     或显式指定 provider="workbuddy" 时，自动调用本地 wb-proxy 网关已封装的 MCP 搜索入口
     （POST http://127.0.0.1:8788/mcp -> web_search，底层为 WorkBuddy 官方 /agenttool/v1/search）。
3. 鉴权边界严格隔离：
   - DEEPSEEK_API_KEY（进程环境变量 -> 用户环境注册表 -> 系统环境注册表）仅发往 DeepSeek API；
   - 本地 wb-proxy 网关鉴权（WB_PROXY_API_KEY / WORK_BUDDY_API_KEY / 本地 wb-proxy settings.json）
     仅发往本机回环或显式配置的网关地址，绝不外泄。
4. stdout 是 MCP 协议通道，任何日志只能走 stderr；本文件不 print 到 stdout。
5. 工具 ID 直接使用品牌别名 DeepSeek-Search / DeepSeek-Fetch，完整调用名是
   mcp__deepseek__DeepSeek-Search / mcp__deepseek__DeepSeek-Fetch；
   权限规则统一用 mcp__deepseek__* 覆盖。
6. 计费口径与官方一致：仅主通道 DeepSeek 官方 HTTP 200 且 Search 的 results 非空 /
   Fetch 的 content 非空，才计一次成功；降级到 WorkBuddy 网关搜索不计入官方扣费统计。
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from usage_store import record_success

VERSION = "1.2.0"

# 显式自定义网关必须可信且使用 HTTPS；不会跟随任何重定向。
BASE_URL = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")

# 本地 wb-proxy 网关 MCP 搜索入口与默认配置文件路径。
WB_MCP_URL = (
    os.environ.get("WB_PROXY_MCP_URL", "http://127.0.0.1:8788/mcp").strip()
    or "http://127.0.0.1:8788/mcp"
)
DEFAULT_WB_SETTINGS_PATH = r"D:\Tools\AI\wb-proxy-v1.6.10\wb-proxy\accounts\settings.json"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_HTTP = urllib.request.build_opener(_NoRedirect())
# 本机回环专用 opener：绕过系统 HTTP_PROXY/HTTPS_PROXY，防止 127.0.0.1 请求误走外部代理。
_LOOPBACK_HTTP = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _NoRedirect(),
)


def _endpoint(path: str) -> str:
    parsed = urllib.parse.urlsplit(BASE_URL)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in BASE_URL)
    ):
        raise ValueError("invalid API base")
    _ = parsed.port
    return f"{BASE_URL}{path}"


def _wb_endpoint() -> tuple[str, bool]:
    """校验并返回 (wb_mcp_url, is_loopback)。仅允许回环 HTTP/HTTPS 或外部 HTTPS。"""
    raw = (WB_MCP_URL or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    host = (parsed.hostname or "").lower()
    is_loopback = host in LOOPBACK_HOSTS
    if (
        not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in raw)
    ):
        raise ValueError("invalid WB_MCP_URL")
    if parsed.scheme == "http" and not is_loopback:
        raise ValueError("non-loopback WB_MCP_URL must use https")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("invalid WB_MCP_URL scheme")
    _ = parsed.port
    return raw, is_loopback


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
    return value if math.isfinite(value) and value > 0 else default


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
WB_TIMEOUT_SECONDS = _env_float("WB_PROXY_SEARCH_TIMEOUT", 25.0)
# Leave time for serialization and usage accounting within the Host's 90s call limit.
REQUEST_BUDGET_SECONDS = 80.0
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
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


def _valid_ascii_token(token: str) -> bool:
    return bool(token) and token.isascii() and not any(ord(c) <= 32 or ord(c) == 127 for c in token)


def _wb_api_key(is_loopback: bool = True) -> str:
    """读取本地 wb-proxy 网关鉴权 Key。

    优先级：
    1. 环境变量 WB_PROXY_API_KEY / WORK_BUDDY_API_KEY
    2. Windows 注册表环境变量 WB_PROXY_API_KEY / WORK_BUDDY_API_KEY
    3. 仅当目标为本机回环（is_loopback=True）时，按需读取本地 wb-proxy 的 settings.json
    """
    for var_name in ("WB_PROXY_API_KEY", "WORK_BUDDY_API_KEY"):
        val = os.environ.get(var_name, "").strip()
        if _valid_ascii_token(val):
            return val
    for var_name in ("WB_PROXY_API_KEY", "WORK_BUDDY_API_KEY"):
        val = _windows_env(var_name)
        if _valid_ascii_token(val):
            return val
    if not is_loopback:
        return ""

    settings_path_raw = (
        os.environ.get("WB_PROXY_SETTINGS_PATH", "").strip()
        or _windows_env("WB_PROXY_SETTINGS_PATH")
        or DEFAULT_WB_SETTINGS_PATH
    )
    try:
        settings_path = Path(settings_path_raw)
        if not settings_path.is_file():
            return ""
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return ""
        api_keys = data.get("api_keys")
        if isinstance(api_keys, list):
            enabled_keys: list[tuple[str, str]] = []
            for entry in api_keys:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("enabled", True) or entry.get("deleted_at"):
                    continue
                k = str(entry.get("key") or "").strip()
                if _valid_ascii_token(k):
                    name = str(entry.get("name") or "").strip().lower()
                    enabled_keys.append((name, k))
            for name, k in enabled_keys:
                if "deepseek" in name or "dsh" in name:
                    return k
            if enabled_keys:
                return enabled_keys[0][1]
        if data.get("api_key_set"):
            legacy = str(data.get("api_key") or "").strip()
            if _valid_ascii_token(legacy):
                return legacy
    except Exception:
        return ""
    return ""


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


def _clean_domains(domains: Any) -> list[str]:
    """清洗域名列表，过滤空白与非法项。"""
    if not domains:
        return []
    if isinstance(domains, str):
        domains = [d.strip() for d in domains.split(",") if d.strip()]
    if not isinstance(domains, (list, tuple)):
        return []
    out: list[str] = []
    for item in domains:
        d = str(item or "").strip().lower()
        if not d:
            continue
        d = re.sub(r"^https?://", "", d).split("/")[0].strip()
        if d and not any(c.isspace() for c in d) and d not in out:
            out.append(d)
    return out


def _apply_domain_filters_to_query(
    query: str,
    allowed_domains: list[str],
    blocked_domains: list[str],
    max_len: int = 128,
) -> str:
    """在不超过 max_len 的前提下，把 allowed/blocked 域名编译为 site:/-site: 追加到 query。"""
    q = query.strip()
    if not allowed_domains and not blocked_domains:
        return q
    extras: list[str] = []
    if allowed_domains and "site:" not in q.lower():
        if len(allowed_domains) == 1:
            extras.append(f"site:{allowed_domains[0]}")
        else:
            extras.append("(" + " OR ".join(f"site:{d}" for d in allowed_domains) + ")")
    for d in blocked_domains:
        token = f"-site:{d}"
        if token.lower() not in q.lower():
            extras.append(token)
    if not extras:
        return q
    candidate = f"{q} {' '.join(extras)}".strip()
    if len(candidate) <= max_len:
        return candidate
    return q


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
    if not _valid_ascii_token(key):
        return {"error": "invalid_api_key", "message": "专用 API Key 格式无效，请检查环境变量设置。"}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    attempts = MAX_RETRIES + 1
    last: dict[str, Any] | None = None
    deadline = time.monotonic() + REQUEST_BUDGET_SECONDS
    exhausted = {"error": "timeout", "message": "请求与重试已用尽本次调用时间预算。"}

    for attempt in range(attempts):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return exhausted
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
            with _HTTP.open(request, timeout=min(TIMEOUT_SECONDS, remaining)) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
            if time.monotonic() >= deadline:
                return exhausted
            if len(data) > MAX_RESPONSE_BYTES:
                return {"error": "response_too_large", "message": "接口响应超过大小上限。"}
            raw = data.decode("utf-8", errors="replace")
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
        if delay >= deadline - time.monotonic():
            return exhausted
        print(
            f"[deepseek-tools] {path} 第 {attempt + 1}/{attempts} 次失败，{delay:.2f}s 后重试。",
            file=sys.stderr,
        )
        time.sleep(delay)

    return last or {"error": "unknown", "message": "请求未产生结果。"}


_ITEM_HEADER_RE = re.compile(r"^\d+\.\s+(?P<rest>.+)$")


def _parse_wb_markdown_results(text: str) -> list[dict[str, Any]]:
    """兼容解析 wb_search.format_search_results_markdown 生成的 Markdown 文本。"""
    text = (text or "").strip()
    if not text or text.startswith("No web search results found for query:"):
        return []
    lines = text.splitlines()
    results: list[dict[str, Any]] = []
    current_header: str | None = None
    current_url = ""
    current_snippet_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_header, current_url, current_snippet_lines
        if current_header is None:
            return
        rest = current_header.strip()
        title = rest
        site_name = ""
        published_time = ""
        if current_url:
            marker = f"]({current_url})"
            if rest.startswith("[") and marker in rest:
                idx = rest.find(marker)
                title = rest[1:idx].strip() or "Untitled"
                tail = rest[idx + len(marker) :].strip()
                if tail.startswith("(") and tail.endswith(")"):
                    meta = tail[1:-1].strip()
                    parts = [p.strip() for p in meta.split("|") if p.strip()]
                    if len(parts) == 1:
                        site_name = parts[0]
                    elif len(parts) >= 2:
                        site_name = parts[0]
                        published_time = " | ".join(parts[1:])
        results.append(
            {
                "title": title,
                "url": current_url,
                "snippet": "\n".join(current_snippet_lines).strip(),
                "site_name": site_name,
                "published_time": published_time,
            }
        )
        current_header = None
        current_url = ""
        current_snippet_lines = []

    for line in lines:
        if line.startswith("Web search results for query:"):
            continue
        m = _ITEM_HEADER_RE.match(line)
        if m:
            _flush()
            current_header = m.group("rest")
            continue
        if current_header is not None:
            if line.startswith("   URL: ") and not current_url:
                current_url = line[len("   URL: ") :].strip()
            elif line.startswith("   "):
                current_snippet_lines.append(line[3:])
            elif line.strip():
                current_snippet_lines.append(line.strip())
    _flush()
    return results


def _normalize_wb_results(raw_results: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("snippet") or ""),
                "site_name": str(item.get("site_name") or ""),
                "published_time": str(item.get("published_time") or ""),
            }
        )
    return out


def _wb_search(
    query: str,
    count: int = 10,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
    freshness: str = "",
    trigger_mode: str = "direct",
) -> dict[str, Any]:
    """调用本地 wb-proxy 网关 MCP 搜索入口（底层为 WorkBuddy 官方 /agenttool/v1/search）。"""
    try:
        endpoint, is_loopback = _wb_endpoint()
    except ValueError:
        return {"error": "invalid_wb_mcp_url", "message": "本地网关 MCP 地址格式无效。"}

    wb_key = _wb_api_key(is_loopback=is_loopback)
    arguments: dict[str, Any] = {
        "query": query,
        "count": max(1, min(20, int(count))),
    }
    if allowed_domains:
        arguments["allowed_domains"] = allowed_domains
    if blocked_domains:
        arguments["blocked_domains"] = blocked_domains
    if freshness:
        arguments["freshness"] = freshness

    rpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "web_search",
            "arguments": arguments,
        },
    }
    body = json.dumps(rpc_payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"Juzi-DeepSeek-Tools/{VERSION}",
        "X-WB-Search-Trigger": str(trigger_mode or "direct")[:60],
    }
    if wb_key:
        headers["Authorization"] = f"Bearer {wb_key}"

    request = urllib.request.Request(
        url=endpoint,
        data=body,
        method="POST",
        headers=headers,
    )
    opener = _LOOPBACK_HTTP if is_loopback else _HTTP
    try:
        with opener.open(request, timeout=WB_TIMEOUT_SECONDS) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            return {"error": "wb_response_too_large", "message": "本地网关搜索响应超过大小上限。"}
        raw = data.decode("utf-8", errors="replace")
        if not raw:
            return {"error": "wb_empty_response", "message": "本地网关返回了空响应体。"}
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {"error": "wb_invalid_response", "message": "本地网关响应不是 JSON 对象。"}
        if wb_key and wb_key in json.dumps(parsed, ensure_ascii=False):
            return {"error": "unsafe_response", "message": "接口响应包含鉴权信息，已阻止返回。"}
        if "error" in parsed:
            err_obj = parsed.get("error")
            msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
            return {"error": "wb_rpc_error", "message": str(msg or "MCP JSON-RPC error")}
        res_obj = parsed.get("result")
        if not isinstance(res_obj, dict):
            return {"error": "wb_invalid_result", "message": "本地网关未返回有效的 MCP result。"}
        if res_obj.get("isError"):
            content_list = res_obj.get("content")
            err_text = "WorkBuddy search tool error"
            if isinstance(content_list, list) and content_list and isinstance(content_list[0], dict):
                err_text = str(content_list[0].get("text") or err_text)
            return {"error": "wb_tool_error", "message": err_text}
        if isinstance(res_obj.get("results"), list):
            return {"results": _normalize_wb_results(res_obj["results"])}
        content_list = res_obj.get("content")
        text_out = ""
        if isinstance(content_list, list):
            for block in content_list:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_out = str(block.get("text") or "")
                    break
        return {"results": _parse_wb_markdown_results(text_out)}
    except urllib.error.HTTPError as exc:
        exc.close()
        return {
            "error": "wb_http_error",
            "status": exc.code,
            "message": "本地网关拒绝搜索请求或返回错误状态码。",
        }
    except TimeoutError:
        return {"error": "wb_timeout", "message": f"本地网关搜索超过 {WB_TIMEOUT_SECONDS:g} 秒。"}
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            return {"error": "wb_timeout", "message": f"本地网关搜索超过 {WB_TIMEOUT_SECONDS:g} 秒。"}
        return {"error": "wb_network_error", "message": "无法连接本地 wb-proxy 网关（127.0.0.1:8788）。"}
    except Exception:
        return {"error": "wb_unknown_error", "message": "调用本地网关搜索时发生异常。"}


@mcp.tool(
    name="DeepSeek-Search",
    title="DeepSeek-Search",
    description=(
        "DeepSeek-Search：调用 DeepSeek 官方搜索接口（不可用时自动降级至本地 WorkBuddy 网关搜索），"
        "返回带标题、URL、摘要、发布时间、权威性和重排分数的结构化结果。"
        "支持 site:、-site:、引号等语法，以及 allowed_domains/blocked_domains/freshness 过滤。"
    ),
)
def search(
    query: str,
    count: int = 10,
    need_content: bool = False,
    ori_question: str | None = None,
    localization: str = "",
    max_content_chars: int = 8000,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
    freshness: str = "",
    provider: str = "auto",
) -> str:
    """搜索实时网页（主用 DeepSeek 官方搜索，不可用时自动降级本地 WorkBuddy 网关搜索）。

    Args:
        query: 搜索词，1~128 个 Unicode 字符，不能全为空白。
        count: 返回条数，1~50，默认 10；条数不影响单次计费。
        need_content: 是否在每条结果里返回网页正文；默认 False 节省上下文。
        ori_question: 触发搜索的用户原始问题（1~128 字符），帮助理解搜索意图。
        localization: 用于优先本地化结果的 IP 地址，默认空字符串。
        max_content_chars: need_content=True 时每条正文最多保留多少字符，
            0 表示不截断；默认 8000，避免一次搜索撑爆上下文。
        allowed_domains: 可选，仅搜索指定域名列表（如 ["github.com", "python.org"]）。
        blocked_domains: 可选，排除指定域名列表（如 ["csdn.net"]）。
        freshness: 可选，时间过滤（如 "d" 一天内、"d7" 一周内、"m" 一月内、"y" 一年内）。
        provider: 搜索通道策略，"auto"（默认：DeepSeek 优先，不可用自动降级 WorkBuddy）、
            "deepseek"（仅 DeepSeek 官方）或 "workbuddy"（直接走本地 WorkBuddy 网关）。
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

    provider_mode = (provider or "auto").strip().lower() if isinstance(provider, str) else "auto"
    if provider_mode not in ("auto", "deepseek", "workbuddy"):
        return _dump({"error": "invalid_provider", "message": "provider 必须是 auto、deepseek 或 workbuddy。"})

    clean_allowed = _clean_domains(allowed_domains)
    clean_blocked = _clean_domains(blocked_domains)
    clean_freshness = (freshness or "").strip() if isinstance(freshness, str) else ""

    if provider_mode == "workbuddy":
        wb_res = _wb_search(
            query=query,
            count=min(count_value, 20),
            allowed_domains=clean_allowed,
            blocked_domains=clean_blocked,
            freshness=clean_freshness,
        )
        if "error" in wb_res:
            return _dump(wb_res)
        wb_results = wb_res.get("results") or []
        return _dump(
            {
                "source": "workbuddy",
                "query": query,
                "count": len(wb_results),
                "results": wb_results,
            }
        )

    limit = _as_int(max_content_chars, 8000)
    effective_query = _apply_domain_filters_to_query(query, clean_allowed, clean_blocked, max_len=128)

    payload: dict[str, Any] = {
        "query": effective_query,
        "count": count_value,
        "need_content": bool(need_content),
        "localization": localization if isinstance(localization, str) else "",
    }
    if ori_question:
        payload["ori_question"] = ori_question

    result = _post("/v1/tools/search", payload)
    if "error" in result:
        if provider_mode == "auto":
            status_suffix = f":{result['status']}" if "status" in result else ""
            reason = f"{result.get('error', 'unavailable')}{status_suffix}"
            wb_res = _wb_search(
                query=query,
                count=min(count_value, 20),
                allowed_domains=clean_allowed,
                blocked_domains=clean_blocked,
                freshness=clean_freshness,
                trigger_mode=f"fallback:{reason}",
            )
            if "error" not in wb_res:
                wb_results = wb_res.get("results") or []
                print(
                    f"[deepseek-tools] DeepSeek-Search 主通道不可用 ({reason})，已自动降级至本地 WorkBuddy 网关搜索。",
                    file=sys.stderr,
                )
                return _dump(
                    {
                        "source": "workbuddy_fallback",
                        "fallback_reason": reason,
                        "query": query,
                        "count": len(wb_results),
                        "results": wb_results,
                    }
                )
        return _dump(result)

    results = result.get("results")
    if not isinstance(results, list):
        results = []
    results = [item for item in results if isinstance(item, dict)]

    # 计费口径：仅 DeepSeek 官方主通道 HTTP 200 且 results 非空才算一次成功搜索。
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
