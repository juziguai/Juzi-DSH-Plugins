#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 Python 标准库 Chrome DevTools Protocol (CDP) 客户端。

直接通过本地 Chrome/Edge 144+ 的 `DevToolsActivePort` WebSocket 连接已登录浏览器：
- 零第三方依赖（仅用 socket / hashlib / base64 / json 等标准库），保持 MCP <0.5s 极速启动；
- 单一常驻 Browser WebSocket 连接 + Target flatten 会话复用，避免每次调用重复弹窗授权；
- 支持穿透 Shadow DOM 的轻量页面语义/可访问性采集（`inspect_page`），后台免抢鼠标操作网页。
"""

from __future__ import annotations

import atexit
import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import security

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_WS_FRAME_BYTES = 32 * 1024 * 1024

FORBIDDEN_URL_PREFIXES = (
    "chrome://settings/passwords",
    "chrome://password-manager",
    "edge://settings/passwords",
    "edge://wallet/passwords",
    "brave://settings/passwords",
)


class CdpError(RuntimeError):
    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.extra = extra


def forbidden_page_reason(url: str | None, title: str | None) -> str | None:
    raw_url = (url or "").strip()
    low_url = raw_url.lower()
    for prefix in FORBIDDEN_URL_PREFIXES:
        if low_url.startswith(prefix):
            return f"禁止访问受保护的浏览器密码页面：{raw_url}"
    title_check = security.forbidden_reason({"process": "chrome.exe", "title": title or ""})
    if title_check:
        return title_check
    if low_url.startswith(("chrome-extension://", "extension://")):
        low_title = (title or "").casefold()
        for part in security.FORBIDDEN_TITLE_PARTS:
            if part.casefold() in low_title:
                return f"禁止操作受保护扩展页面：{title}"
    return None


def _default_port_files(browser: str = "auto") -> list[tuple[str, Path]]:
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    candidates = {
        "chrome": [
            ("chrome", local / "Google" / "Chrome" / "User Data" / "DevToolsActivePort"),
            ("chrome-beta", local / "Google" / "Chrome Beta" / "User Data" / "DevToolsActivePort"),
            ("chrome-canary", local / "Google" / "Chrome SxS" / "User Data" / "DevToolsActivePort"),
        ],
        "edge": [
            ("edge", local / "Microsoft" / "Edge" / "User Data" / "DevToolsActivePort"),
        ],
    }
    mode = (browser or "auto").strip().lower()
    if mode == "edge":
        return candidates["edge"]
    if mode == "chrome":
        return candidates["chrome"]
    return candidates["chrome"] + candidates["edge"]


def discover_ws_endpoint(browser: str = "auto", ws_url: str | None = None, port: int | None = None) -> tuple[str, str]:
    """返回 (browser_kind, ws://127.0.0.1:<port>/devtools/browser/...)。"""
    if ws_url:
        parsed = urlparse(ws_url.strip())
        if parsed.scheme not in ("ws",) or parsed.hostname not in ("127.0.0.1", "localhost"):
            raise CdpError("invalid_ws_url", "仅允许连接本机 ws://127.0.0.1 或 localhost 的调试端点。")
        return ("custom", ws_url.strip())

    for kind, path in _default_port_files(browser):
        if not path.exists():
            continue
        try:
            lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        except OSError:
            continue
        if len(lines) < 2:
            continue
        try:
            file_port = int(lines[0])
        except ValueError:
            continue
        if port is not None and file_port != int(port):
            continue
        ws_path = lines[1] if lines[1].startswith("/") else f"/{lines[1]}"
        # 探测端口是否真有活动监听（排除浏览器异常退出残留的旧文件）
        try:
            with socket.create_connection(("127.0.0.1", file_port), timeout=0.6):
                return (kind, f"ws://127.0.0.1:{file_port}{ws_path}")
        except OSError:
            continue

    raise CdpError(
        "cdp_unavailable",
        (
            "未检测到开启远程调试的本地 Chrome/Edge（缺少活动 DevToolsActivePort）。"
            "请在 Chrome 地址栏打开 chrome://inspect/#remote-debugging 并勾选启用远程调试，"
            "或回退使用 inspect_ui（Windows UIA）。"
        ),
    )


class _LocalWebSocket:
    """面向本机 CDP 的纯标准库 RFC 6455 WebSocket 客户端。"""

    def __init__(self, url: str, connect_timeout: float = 25.0) -> None:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        sock = socket.create_connection((host, port), timeout=connect_timeout)
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            raw_key = os.urandom(16)
            ws_key = base64.b64encode(raw_key).decode("ascii")
            request = (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {ws_key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            )
            sock.sendall(request.encode("ascii"))

            header_buf = bytearray()
            while b"\r\n\r\n" not in header_buf:
                chunk = sock.recv(4096)
                if not chunk:
                    raise CdpError(
                        "cdp_handshake_closed",
                        "Chrome 关闭了远程调试握手（可能在浏览器确认框中点了拒绝，或尚未点允许）。",
                    )
                header_buf.extend(chunk)
                if len(header_buf) > 65536:
                    raise CdpError("cdp_handshake_failed", "WebSocket 握手响应头过大。")

            sep = header_buf.index(b"\r\n\r\n")
            raw_headers = bytes(header_buf[:sep]).decode("latin-1")
            self._rx_buf = bytearray(header_buf[sep + 4:])

            lines = raw_headers.split("\r\n")
            status_line = lines[0] if lines else ""
            if " 101 " not in status_line:
                raise CdpError(
                    "cdp_handshake_rejected",
                    f"Chrome 拒绝了远程调试连接（{status_line}）；请确认已在浏览器弹窗中点击允许。",
                )
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            expected_accept = base64.b64encode(
                hashlib.sha1((ws_key + _WS_GUID).encode("ascii")).digest()
            ).decode("ascii")
            if headers.get("sec-websocket-accept") != expected_accept:
                raise CdpError("cdp_handshake_failed", "WebSocket Sec-WebSocket-Accept 校验不匹配。")
        except socket.timeout as exc:
            sock.close()
            raise CdpError(
                "cdp_permission_timeout",
                "等待 Chrome 远程调试授权超时：请看一眼 Chrome 窗口弹出的「允许远程调试？」提示并点击允许后再试。",
            ) from exc
        except Exception:
            sock.close()
            raise

        self._sock: socket.socket | None = sock

    @property
    def closed(self) -> bool:
        return self._sock is None

    def close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is None:
            return
        try:
            self._send_frame(0x8, b"")
        except Exception:  # noqa: BLE001
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _read_exact(self, count: int, timeout: float) -> bytes:
        sock = self._sock
        if sock is None:
            raise CdpError("cdp_closed", "WebSocket 连接已关闭。")
        sock.settimeout(timeout)
        while len(self._rx_buf) < count:
            chunk = sock.recv(max(4096, min(65536, count - len(self._rx_buf))))
            if not chunk:
                self.close()
                raise CdpError("cdp_closed", "Chrome 断开了远程调试连接。")
            self._rx_buf.extend(chunk)
        out = bytes(self._rx_buf[:count])
        del self._rx_buf[:count]
        return out

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        sock = self._sock
        if sock is None:
            raise CdpError("cdp_closed", "WebSocket 连接已关闭。")
        length = len(payload)
        header = bytearray([0x80 | (opcode & 0x0F)])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        if length:
            masked = bytearray(payload)
            m0, m1, m2, m3 = mask
            for i in range(length):
                rem = i & 3
                masked[i] ^= m0 if rem == 0 else (m1 if rem == 1 else (m2 if rem == 2 else m3))
            header.extend(masked)
        sock.settimeout(10.0)
        sock.sendall(header)

    def send_text(self, text: str) -> None:
        self._send_frame(0x1, text.encode("utf-8"))

    def recv_text(self, timeout: float = 15.0) -> str:
        fragments: list[bytes] = []
        while True:
            first2 = self._read_exact(2, timeout)
            fin = bool(first2[0] & 0x80)
            opcode = first2[0] & 0x0F
            masked = bool(first2[1] & 0x80)
            length = first2[1] & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2, timeout))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8, timeout))[0]
            if length > MAX_WS_FRAME_BYTES:
                self.close()
                raise CdpError("cdp_frame_too_large", f"CDP 响应帧超过上限（{length} bytes）。")
            mask_key = self._read_exact(4, timeout) if masked else b""
            payload = self._read_exact(length, timeout) if length else b""
            if masked and payload:
                arr = bytearray(payload)
                for i in range(length):
                    arr[i] ^= mask_key[i & 3]
                payload = bytes(arr)

            if opcode == 0x8:  # CLOSE
                self.close()
                raise CdpError("cdp_closed", "Chrome 主动关闭了调试会话。")
            if opcode == 0x9:  # PING
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:  # PONG
                continue
            if opcode in (0x0, 0x1, 0x2):
                fragments.append(payload)
                if fin:
                    return b"".join(fragments).decode("utf-8", errors="replace")


# 穿透 Shadow DOM 的极速页面交互与文本采集脚本（只把临时引用存于 window.__juziCdpRefs，不修改任何真实 DOM 属性）
_INSPECT_DOM_JS = r"""
((opts) => {
  const query = (opts.query || '').trim().toLowerCase();
  const interactiveOnly = !!opts.interactiveOnly;
  const includeText = opts.includeText !== false;
  const maxElements = Math.min(Math.max(opts.maxElements || 150, 1), 500);

  const INTERACTIVE_TAGS = new Set(['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'SUMMARY', 'OPTION']);
  const INTERACTIVE_ROLES = new Set([
    'button', 'link', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
    'radio', 'checkbox', 'switch', 'tab', 'combobox', 'textbox', 'searchbox',
    'option', 'slider', 'spinbutton', 'treeitem'
  ]);

  const clean = (s, maxLen = 120) => {
    if (!s) return '';
    const t = String(s).replace(/[\s\u00a0]+/g, ' ').trim();
    return t.length > maxLen ? t.slice(0, maxLen - 1) + '…' : t;
  };

  const isVisible = (el) => {
    if (!el || el.nodeType !== 1) return false;
    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return false;
    const style = window.getComputedStyle(el);
    if (!style || style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
      return false;
    }
    const r = el.getBoundingClientRect();
    return r.width >= 2 && r.height >= 2 && r.bottom > 0 && r.right > 0
      && r.top < (window.innerHeight || 1440) && r.left < (window.innerWidth || 2560);
  };

  const isDisabled = (el) => {
    if (el.disabled === true) return true;
    const aria = el.getAttribute('aria-disabled');
    if (aria === 'true') return true;
    if (el.hasAttribute('disabled')) return true;
    return false;
  };

  const roleOf = (el) => {
    const explicit = (el.getAttribute('role') || '').trim().toLowerCase();
    if (explicit) return explicit;
    const tag = el.tagName;
    if (tag === 'A' && el.hasAttribute('href')) return 'link';
    if (tag === 'BUTTON') return 'button';
    if (tag === 'SELECT') return 'combobox';
    if (tag === 'TEXTAREA') return 'textbox';
    if (tag === 'INPUT') {
      const tp = (el.type || 'text').toLowerCase();
      if (tp === 'radio') return 'radio';
      if (tp === 'checkbox') return 'checkbox';
      if (tp === 'button' || tp === 'submit' || tp === 'reset') return 'button';
      return 'textbox';
    }
    if (el.isContentEditable) return 'textbox';
    // Material / Lit 自定义组件兜底识别
    const lowTag = tag.toLowerCase();
    if (lowTag.includes('button') || lowTag.includes('icon-button') || lowTag.includes('fab')) return 'button';
    if (lowTag.includes('radio')) return 'radio';
    if (lowTag.includes('checkbox') || lowTag.includes('switch')) return 'checkbox';
    if (lowTag.includes('menu-item') || lowTag.includes('list-item')) return 'menuitem';
    if (lowTag.includes('tab')) return 'tab';
    return '';
  };

  const labelOf = (el) => {
    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.trim()) return clean(ariaLabel);
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const root = el.getRootNode && el.getRootNode() ? el.getRootNode() : document;
      const parts = labelledBy.split(/\s+/).map(id => {
        const refEl = (root.getElementById ? root.getElementById(id) : null) || document.getElementById(id);
        return refEl ? (refEl.innerText || refEl.textContent || '') : '';
      }).filter(Boolean);
      if (parts.length) return clean(parts.join(' '));
    }
    if (el.id) {
      const root = el.getRootNode && el.getRootNode() ? el.getRootNode() : document;
      const lbl = root.querySelector ? root.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
      if (lbl) return clean(lbl.innerText || lbl.textContent || '');
    }
    const wrappingLabel = el.closest ? el.closest('label') : null;
    if (wrappingLabel) {
      const txt = clean(wrappingLabel.innerText || wrappingLabel.textContent || '');
      if (txt) return txt;
    }
    const placeholder = el.getAttribute('placeholder') || el.getAttribute('title');
    const ownText = clean(el.innerText || el.textContent || '');
    return ownText || clean(placeholder || '');
  };

  const refs = {};
  let nextRef = 1;
  const lines = [];
  const items = [];
  const seen = new Set();

  const walk = (root) => {
    if (!root || items.length >= maxElements) return;
    const children = root.children || [];
    for (let i = 0; i < children.length && items.length < maxElements; i++) {
      const el = children[i];
      const style = window.getComputedStyle(el);
      if (style && style.display === 'none') continue;

      const role = roleOf(el);
      const interactive = INTERACTIVE_TAGS.has(el.tagName)
        || INTERACTIVE_ROLES.has(role)
        || el.isContentEditable
        || (el.tabIndex >= 0 && role !== '');

      if (interactive && isVisible(el)) {
        const name = labelOf(el);
        const isPwd = el.tagName === 'INPUT' && (el.type || '').toLowerCase() === 'password';
        const val = isPwd ? '' : clean(el.value !== undefined && el.tagName !== 'BUTTON' && el.tagName !== 'LI' ? el.value : '', 80);
        const disabled = isDisabled(el);
        const selected = el.selected === true || el.getAttribute('aria-selected') === 'true'
          || (role === 'radio' && (el.checked === true || el.getAttribute('aria-checked') === 'true'));
        const checkedAttr = el.getAttribute('aria-checked');
        const checked = role === 'checkbox' || role === 'switch'
          ? (el.checked === true || checkedAttr === 'true' ? 'on' : 'off')
          : null;
        const expandedAttr = el.getAttribute('aria-expanded');
        const expanded = expandedAttr === 'true' ? true : (expandedAttr === 'false' ? false : null);

        const matchOk = !query
          || name.toLowerCase().includes(query)
          || val.toLowerCase().includes(query)
          || role.toLowerCase().includes(query);

        const r = el.getBoundingClientRect();
        const cx = Math.round(r.left + r.width / 2);
        const cy = Math.round(r.top + r.height / 2);
        const dedup = `${role || el.tagName.toLowerCase()}|${name}|${Math.round(cx / 6)}|${Math.round(cy / 6)}`;

        if (matchOk && (name || val || role) && !seen.has(dedup)) {
          seen.add(dedup);
          const id = nextRef++;
          refs[id] = el;
          const kind = role || el.tagName.toLowerCase();
          let desc = `[${id}] ${kind}`;
          if (name) desc += ` "${name.replace(/"/g, "'")}"`;
          if (!isPwd && val && val !== name) desc += ` val="${val.replace(/"/g, "'")}"`;
          if (disabled) desc += ' [DISABLED]';
          if (selected) desc += ' [selected]';
          if (checked) desc += ` [checked=${checked}]`;
          if (expanded !== null) desc += expanded ? ' [expanded]' : ' [collapsed]';
          if (isPwd) desc += ' [password]';
          lines.push(desc);
          items.push({ ref: id, role: kind, name, cx, cy, enabled: !disabled, selected, checked, expanded });
        }
      } else if (!interactiveOnly && includeText && isVisible(el) && !el.shadowRoot) {
        // 采集没有子元素包裹的叶子可见文本块
        let directText = '';
        for (let n = el.firstChild; n; n = n.nextSibling) {
          if (n.nodeType === 3 && n.nodeValue.trim()) {
            directText += ' ' + n.nodeValue.trim();
          }
        }
        directText = clean(directText, 140);
        if (directText && (!query || directText.toLowerCase().includes(query))) {
          const r = el.getBoundingClientRect();
          const cx = Math.round(r.left + r.width / 2);
          const cy = Math.round(r.top + r.height / 2);
          const dedup = `text|${directText}|${Math.round(cy / 8)}`;
          if (!seen.has(dedup)) {
            seen.add(dedup);
            lines.push(`    text "${directText.replace(/"/g, "'")}"`);
            items.push({ ref: null, role: 'text', name: directText, cx, cy, enabled: true });
          }
        }
      }

      if (el.shadowRoot) {
        walk(el.shadowRoot);
      }
      walk(el);
    }
  };

  walk(document.body || document.documentElement);
  window.__juziCdpRefs = refs;
  return {
    title: document.title || '',
    url: location.href || '',
    ready_state: document.readyState || '',
    count: items.length,
    compact: lines.join('\n'),
    elements: items
  };
})
"""

_RESOLVE_TARGET_JS = r"""
((opts) => {
  const clean = (s) => String(s || '').replace(/[\s\u00a0]+/g, ' ').trim();
  let el = null;
  if (opts.ref != null && window.__juziCdpRefs && window.__juziCdpRefs[opts.ref]) {
    el = window.__juziCdpRefs[opts.ref];
    if (!el.isConnected) el = null;
  }
  if (!el && opts.selector) {
    const queryShadow = (root, sel) => {
      try {
        const hit = root.querySelector(sel);
        if (hit) return hit;
      } catch (e) {}
      const children = root.children || [];
      for (let i = 0; i < children.length; i++) {
        if (children[i].shadowRoot) {
          const sub = queryShadow(children[i].shadowRoot, sel);
          if (sub) return sub;
        }
      }
      return null;
    };
    el = queryShadow(document, opts.selector);
  }
  if (!el && opts.text) {
    const needle = opts.text.trim().toLowerCase();
    const matches = [];
    const scan = (root) => {
      const children = root.children || [];
      for (let i = 0; i < children.length; i++) {
        const node = children[i];
        const r = node.getBoundingClientRect();
        if (r.width >= 2 && r.height >= 2) {
          const aria = clean(node.getAttribute('aria-label') || node.getAttribute('placeholder') || node.getAttribute('title'));
          const own = clean(node.innerText || node.textContent || '');
          const exact = (aria && aria.toLowerCase() === needle) || (own && own.toLowerCase() === needle);
          const part = !exact && ((aria && aria.toLowerCase().includes(needle)) || (own && own.toLowerCase().includes(needle) && own.length <= needle.length + 40));
          if (exact || part) {
            const tag = node.tagName.toLowerCase();
            const role = (node.getAttribute('role') || '').toLowerCase();
            const clickable = ['a', 'button', 'input', 'select', 'textarea', 'summary'].includes(tag)
              || ['button', 'link', 'menuitem', 'radio', 'checkbox', 'tab', 'combobox', 'textbox'].includes(role)
              || tag.includes('button') || tag.includes('menu-item') || tag.includes('radio');
            matches.push({ node, exact, clickable, area: r.width * r.height });
          }
        }
        if (node.shadowRoot) scan(node.shadowRoot);
        scan(node);
      }
    };
    scan(document.body || document.documentElement);
    matches.sort((a, b) => (b.exact - a.exact) || (b.clickable - a.clickable) || (a.area - b.area));
    const idx = opts.index || 0;
    if (matches[idx]) el = matches[idx].node;
  }

  if (!el) return { ok: false, error: 'element_not_found', message: '未在当前页面找到目标元素；请先调用 inspect_page 查看最新 [ref] 清单。' };
  const isPwd = el.tagName === 'INPUT' && (el.type || '').toLowerCase() === 'password';
  if (isPwd) return { ok: false, error: 'password_control', message: '安全限制：禁止通过 CDP 操作密码输入框。' };
  const disabled = el.disabled === true || el.getAttribute('aria-disabled') === 'true' || el.hasAttribute('disabled');
  if (disabled) return { ok: false, error: 'element_disabled', message: '目标元素当前处于禁用（DISABLED）状态，无法操作。' };

  try { el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' }); } catch (e) {}
  const r = el.getBoundingClientRect();
  const inViewport = r.width >= 2 && r.height >= 2 && r.top >= 0 && r.left >= 0
    && r.bottom <= (window.innerHeight || 1440) && r.right <= (window.innerWidth || 2560);

  if (opts.mode === 'click_fallback' || !inViewport) {
    el.click();
    return {
      ok: true,
      dispatched_via: 'dom_click',
      tag: el.tagName.toLowerCase(),
      label: clean(el.getAttribute('aria-label') || el.innerText || el.value || '').slice(0, 80),
      cx: Math.round(r.left + r.width / 2),
      cy: Math.round(r.top + r.height / 2)
    };
  }

  if (opts.mode === 'fill') {
    el.focus();
    const text = String(opts.fillText ?? '');
    if (el.isContentEditable) {
      el.textContent = text;
    } else {
      const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      const setter = proto && Object.getOwnPropertyDescriptor(proto, 'value') ? Object.getOwnPropertyDescriptor(proto, 'value').set : null;
      if (setter) setter.call(el, text);
      else el.value = text;
    }
    el.dispatchEvent(new InputEvent('input', { bubbles: true, composed: true, data: text, inputType: 'insertText' }));
    el.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
    return {
      ok: true,
      tag: el.tagName.toLowerCase(),
      characters: text.length
    };
  }

  return {
    ok: true,
    dispatched_via: 'cdp_mouse',
    tag: el.tagName.toLowerCase(),
    label: clean(el.getAttribute('aria-label') || el.innerText || el.value || '').slice(0, 80),
    cx: Math.round(r.left + r.width / 2),
    cy: Math.round(r.top + r.height / 2)
  };
})
"""


class CdpManager:
    """管理单条常驻 Browser WebSocket 连接及 flatten Target 会话。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ws: _LocalWebSocket | None = None
        self._ws_url: str | None = None
        self._browser_kind: str | None = None
        self._next_id = 0
        self._sessions: dict[str, str] = {}  # targetId -> sessionId

    def close(self) -> None:
        with self._lock:
            self._reset_unlocked()

    def _reset_unlocked(self) -> None:
        ws, self._ws = self._ws, None
        self._ws_url = None
        self._browser_kind = None
        self._sessions.clear()
        if ws is not None:
            ws.close()

    def _ensure_connected_unlocked(self, browser: str = "auto", ws_url: str | None = None, port: int | None = None) -> tuple[str, str]:
        kind, discovered_url = discover_ws_endpoint(browser=browser, ws_url=ws_url, port=port)
        if self._ws is not None and not self._ws.closed and self._ws_url == discovered_url:
            return (self._browser_kind or kind, discovered_url)
        self._reset_unlocked()
        self._ws = _LocalWebSocket(discovered_url, connect_timeout=25.0)
        self._ws_url = discovered_url
        self._browser_kind = kind
        return (kind, discovered_url)

    def _call_unlocked(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        session_id: str | None = None,
        timeout: float = 15.0,
    ) -> dict[str, Any]:
        assert self._ws is not None
        self._next_id += 1
        req_id = self._next_id
        frame: dict[str, Any] = {"id": req_id, "method": method}
        if params:
            frame["params"] = params
        if session_id:
            frame["sessionId"] = session_id
        self._ws.send_text(json.dumps(frame, ensure_ascii=False))

        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CdpError("cdp_timeout", f"CDP 调用 {method} 超时（{timeout}s）。")
            raw = self._ws.recv_text(timeout=remaining)
            msg = json.loads(raw)
            if not isinstance(msg, dict):
                continue
            # 维护会话失效事件
            if msg.get("method") == "Target.detachedFromTarget":
                detached_sid = (msg.get("params") or {}).get("sessionId")
                if detached_sid:
                    for tid, sid in list(self._sessions.items()):
                        if sid == detached_sid:
                            self._sessions.pop(tid, None)
                continue
            if msg.get("id") != req_id:
                continue
            if "error" in msg:
                err = msg["error"] or {}
                err_msg = str(err.get("message") or err)
                raise CdpError("cdp_rpc_error", f"CDP {method} 报错：{err_msg}")
            return msg.get("result") or {}

    def _list_pages_unlocked(self) -> list[dict[str, Any]]:
        res = self._call_unlocked("Target.getTargets")
        pages: list[dict[str, Any]] = []
        for info in res.get("targetInfos") or []:
            if info.get("type") != "page":
                continue
            url = str(info.get("url") or "")
            if url.startswith("devtools://"):
                continue
            pages.append(
                {
                    "target_id": info.get("targetId"),
                    "title": info.get("title") or "",
                    "url": url,
                    "attached": bool(info.get("attached")),
                }
            )
        return pages

    def _resolve_page_unlocked(
        self,
        target_id: str | None = None,
        url_contains: str | None = None,
        title_contains: str | None = None,
    ) -> dict[str, Any]:
        pages = self._list_pages_unlocked()
        if not pages:
            raise CdpError("no_pages", "当前浏览器没有打开的页面标签页。")
        chosen: dict[str, Any] | None = None
        if target_id:
            chosen = next((p for p in pages if p["target_id"] == target_id), None)
            if chosen is None:
                raise CdpError("target_not_found", f"未找到 target_id={target_id} 的标签页，请重新 list_tabs。")
        elif url_contains:
            needle = url_contains.casefold()
            chosen = next((p for p in pages if needle in p["url"].casefold()), None)
            if chosen is None:
                raise CdpError("target_not_found", f"未找到 URL 包含「{url_contains}」的标签页。")
        elif title_contains:
            needle = title_contains.casefold()
            chosen = next((p for p in pages if needle in p["title"].casefold()), None)
            if chosen is None:
                raise CdpError("target_not_found", f"未找到标题包含「{title_contains}」的标签页。")
        else:
            # 默认取第一个非 chrome://newtab 的常规页面，否则取首个
            chosen = next((p for p in pages if not p["url"].startswith(("chrome://", "edge://", "about:"))), pages[0])

        reason = forbidden_page_reason(chosen.get("url"), chosen.get("title"))
        if reason:
            raise CdpError("forbidden_page", reason, page=chosen)
        return chosen

    def _attach_unlocked(self, target_id: str) -> str:
        cached = self._sessions.get(target_id)
        if cached:
            try:
                self._call_unlocked("Runtime.evaluate", {"expression": "1", "returnByValue": True}, session_id=cached, timeout=3.0)
                return cached
            except CdpError:
                self._sessions.pop(target_id, None)
        res = self._call_unlocked("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        sid = str(res.get("sessionId") or "")
        if not sid:
            raise CdpError("attach_failed", f"无法附加到标签页 {target_id}。")
        self._sessions[target_id] = sid
        return sid

    def _eval_js_unlocked(self, session_id: str, fn_source: str, arg_obj: dict[str, Any], timeout: float = 15.0) -> Any:
        expr = f"({fn_source})({json.dumps(arg_obj, ensure_ascii=False)})"
        res = self._call_unlocked(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": True},
            session_id=session_id,
            timeout=timeout,
        )
        if "exceptionDetails" in res:
            details = res["exceptionDetails"] or {}
            exc_text = ((details.get("exception") or {}).get("description")) or details.get("text") or "JS 执行异常"
            raise CdpError("js_eval_error", f"页面脚本执行失败：{str(exc_text)[:300]}")
        return (res.get("result") or {}).get("value")

    def _wait_dom_ready_unlocked(self, session_id: str, wait_ms: int = 1500) -> None:
        deadline = time.monotonic() + max(0.2, min(15.0, wait_ms / 1000.0))
        while time.monotonic() < deadline:
            try:
                state = self._call_unlocked(
                    "Runtime.evaluate",
                    {"expression": "document.readyState", "returnByValue": True},
                    session_id=session_id,
                    timeout=3.0,
                )
                val = (state.get("result") or {}).get("value")
                if val == "complete":
                    return
            except CdpError:
                pass
            time.sleep(0.15)

    def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            for attempt in range(2):
                try:
                    return self._execute_once_unlocked(action, **kwargs)
                except CdpError as exc:
                    if attempt == 0 and exc.code in ("cdp_closed", "cdp_rpc_error") and "closed" in str(exc).lower():
                        self._reset_unlocked()
                        continue
                    raise

    def _execute_once_unlocked(self, action: str, **kwargs: Any) -> dict[str, Any]:
        browser = str(kwargs.get("browser") or "auto")
        ws_url = kwargs.get("ws_url")
        port = kwargs.get("port")
        kind, endpoint = self._ensure_connected_unlocked(browser=browser, ws_url=ws_url, port=port)

        if action == "list_tabs":
            pages = self._list_pages_unlocked()
            return {"ok": True, "browser": kind, "count": len(pages), "tabs": pages}

        if action == "open_url":
            url = str(kwargs.get("url") or "").strip()
            if not url:
                raise CdpError("invalid_url", "open_url 需要非空 url。")
            reason = forbidden_page_reason(url, "")
            if reason:
                raise CdpError("forbidden_page", reason)
            new_tab = bool(kwargs.get("new_tab", True))
            wait_ms = int(kwargs.get("wait_ms", 1800))
            if new_tab and not kwargs.get("target_id"):
                created = self._call_unlocked("Target.createTarget", {"url": url})
                tid = str(created.get("targetId") or "")
            else:
                page = self._resolve_page_unlocked(
                    target_id=kwargs.get("target_id"),
                    url_contains=kwargs.get("url_contains"),
                    title_contains=kwargs.get("title_contains"),
                )
                tid = page["target_id"]
                sid = self._attach_unlocked(tid)
                self._call_unlocked("Page.navigate", {"url": url}, session_id=sid)
            sid = self._attach_unlocked(tid)
            if wait_ms > 0:
                time.sleep(min(1.0, wait_ms / 1000.0))
                self._wait_dom_ready_unlocked(sid, wait_ms=wait_ms)
                extra = max(0, wait_ms - 1000)
                if extra > 0:
                    time.sleep(min(4.0, extra / 1000.0))
            payload: dict[str, Any] = {"ok": True, "action": "open_url", "browser": kind, "target_id": tid, "url": url}
            if kwargs.get("after_inspect", True):
                inspected = self._eval_js_unlocked(sid, _INSPECT_DOM_JS, {
                    "query": kwargs.get("query") or "",
                    "interactiveOnly": bool(kwargs.get("interactive_only", False)),
                    "includeText": bool(kwargs.get("include_text", True)),
                    "maxElements": int(kwargs.get("max_elements", 120)),
                })
                if isinstance(inspected, dict):
                    if not kwargs.get("include_elements", False):
                        inspected.pop("elements", None)
                    payload["page"] = inspected
            return payload

        page = self._resolve_page_unlocked(
            target_id=kwargs.get("target_id"),
            url_contains=kwargs.get("url_contains"),
            title_contains=kwargs.get("title_contains"),
        )
        tid = page["target_id"]

        if action == "activate_tab":
            self._call_unlocked("Target.activateTarget", {"targetId": tid})
            return {"ok": True, "action": "activate_tab", "target_id": tid, "title": page["title"], "url": page["url"]}

        if action == "close_tab":
            self._sessions.pop(tid, None)
            res = self._call_unlocked("Target.closeTarget", {"targetId": tid})
            return {"ok": bool(res.get("success", True)), "action": "close_tab", "target_id": tid}

        sid = self._attach_unlocked(tid)

        if action == "inspect_page":
            t0 = time.perf_counter()
            inspected = self._eval_js_unlocked(sid, _INSPECT_DOM_JS, {
                "query": kwargs.get("query") or "",
                "interactiveOnly": bool(kwargs.get("interactive_only", False)),
                "includeText": bool(kwargs.get("include_text", True)),
                "maxElements": int(kwargs.get("max_elements", 150)),
            })
            elapsed_ms = int(round((time.perf_counter() - t0) * 1000))
            if not isinstance(inspected, dict):
                raise CdpError("inspect_failed", "页面 DOM 采集未返回有效对象。")
            reason = forbidden_page_reason(inspected.get("url"), inspected.get("title"))
            if reason:
                raise CdpError("forbidden_page", reason)
            if not kwargs.get("include_elements", False):
                inspected.pop("elements", None)
            return {"ok": True, "browser": kind, "target_id": tid, "elapsed_ms": elapsed_ms, **inspected}

        if action == "read_text":
            max_chars = max(100, min(100000, int(kwargs.get("max_chars", 8000))))
            data = self._eval_js_unlocked(
                sid,
                "((o) => ({title: document.title || '', url: location.href || '', text: (document.body ? document.body.innerText : '') || ''}))",
                {},
            )
            full_text = str((data or {}).get("text") or "")
            reason = forbidden_page_reason((data or {}).get("url"), (data or {}).get("title"))
            if reason:
                raise CdpError("forbidden_page", reason)
            clipped = full_text[:max_chars]
            return {
                "ok": True,
                "target_id": tid,
                "title": (data or {}).get("title"),
                "url": (data or {}).get("url"),
                "length": len(full_text),
                "truncated": len(full_text) > max_chars,
                "text": clipped,
            }

        if action == "click":
            resolved = self._eval_js_unlocked(sid, _RESOLVE_TARGET_JS, {
                "ref": kwargs.get("ref"),
                "selector": kwargs.get("selector"),
                "text": kwargs.get("text"),
                "index": int(kwargs.get("index", 0)),
                "mode": "click",
            })
            if not isinstance(resolved, dict) or not resolved.get("ok"):
                err = resolved or {}
                raise CdpError(str(err.get("error") or "click_failed"), str(err.get("message") or "未找到可点击元素。"))
            if resolved.get("dispatched_via") == "cdp_mouse":
                cx, cy = int(resolved["cx"]), int(resolved["cy"])
                try:
                    self._call_unlocked("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy, "button": "none"}, session_id=sid)
                    self._call_unlocked("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1}, session_id=sid)
                    self._call_unlocked("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1}, session_id=sid)
                except CdpError:
                    # 窗口最小化等极端情况下回退 DOM click()
                    self._eval_js_unlocked(sid, _RESOLVE_TARGET_JS, {
                        "ref": kwargs.get("ref"),
                        "selector": kwargs.get("selector"),
                        "text": kwargs.get("text"),
                        "index": int(kwargs.get("index", 0)),
                        "mode": "click_fallback",
                    })
                    resolved["dispatched_via"] = "dom_click_fallback"

            wait_ms = max(0, min(10000, int(kwargs.get("wait_ms", 450))))
            if wait_ms > 0:
                time.sleep(wait_ms / 1000.0)
            out: dict[str, Any] = {"ok": True, "action": "click", "target_id": tid, **resolved}
            if kwargs.get("after_inspect", True):
                inspected = self._eval_js_unlocked(sid, _INSPECT_DOM_JS, {
                    "query": kwargs.get("query") or "",
                    "interactiveOnly": bool(kwargs.get("interactive_only", False)),
                    "includeText": bool(kwargs.get("include_text", True)),
                    "maxElements": int(kwargs.get("max_elements", 120)),
                })
                if isinstance(inspected, dict):
                    if not kwargs.get("include_elements", False):
                        inspected.pop("elements", None)
                    out["page"] = inspected
            return out

        if action == "fill":
            fill_text = kwargs.get("value")
            if not isinstance(fill_text, str):
                raise CdpError("invalid_value", "fill 需要字符串参数 value。")
            resolved = self._eval_js_unlocked(sid, _RESOLVE_TARGET_JS, {
                "ref": kwargs.get("ref"),
                "selector": kwargs.get("selector"),
                "text": kwargs.get("text"),
                "index": int(kwargs.get("index", 0)),
                "mode": "fill",
                "fillText": fill_text,
            })
            if not isinstance(resolved, dict) or not resolved.get("ok"):
                err = resolved or {}
                raise CdpError(str(err.get("error") or "fill_failed"), str(err.get("message") or "未找到可输入元素。"))
            if kwargs.get("submit", False):
                self._call_unlocked("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}, session_id=sid)
                self._call_unlocked("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}, session_id=sid)
            return {"ok": True, "action": "fill", "target_id": tid, **resolved}

        if action == "press_key":
            key = str(kwargs.get("key") or "").strip()
            if not key:
                raise CdpError("invalid_key", "press_key 需要非空 key（如 Enter、Escape、Tab、ArrowDown）。")
            vk_map = {"Enter": 13, "Escape": 27, "Tab": 9, "Backspace": 8, "ArrowDown": 40, "ArrowUp": 38, "ArrowLeft": 37, "ArrowRight": 39, " ": 32}
            vk = vk_map.get(key, ord(key.upper()) if len(key) == 1 else 0)
            self._call_unlocked("Input.dispatchKeyEvent", {"type": "keyDown", "key": key, "windowsVirtualKeyCode": vk}, session_id=sid)
            self._call_unlocked("Input.dispatchKeyEvent", {"type": "keyUp", "key": key, "windowsVirtualKeyCode": vk}, session_id=sid)
            return {"ok": True, "action": "press_key", "target_id": tid, "key": key}

        raise CdpError("invalid_action", f"不支持的 chrome_cdp 动作：{action}")


_manager = CdpManager()
close = _manager.close
atexit.register(close)


def execute(action: str, **kwargs: Any) -> dict[str, Any]:
    return _manager.execute(action, **kwargs)
