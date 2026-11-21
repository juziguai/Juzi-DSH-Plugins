#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机 MCP stdio 懒连接远程代理（SSH 隧道桥接远端活动桌面 `juzi-win-dsh`）。

核心特性：
1. 离线零阻塞：本机启动时直接读取本地 `src/core_server.py` 的工具定义，毫秒级响应
   `initialize` / `tools/list` / `ping`，远端关机时绝不拖慢宿主启动。
2. 懒连接 + 长隧道复用：首次收到 `tools/call` 时自动通过 `ssh <target>` 确保远端
   活动桌面回环守护已启动，建立单条 `ssh -N -L` 本地端口转发并完成 Token 鉴权；
   后续请求复用连接。已发送的写操作在断线时报告结果未知。
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PLUGIN_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import core_server  # noqa: E402
from release_paths import release_selector, run_remote_ps


def _retryable_read(params: Any) -> bool:
    if not isinstance(params, dict):
        return False
    name = params.get("name")
    args = params.get("arguments", {})
    if not isinstance(name, str) or not isinstance(args, dict):
        return False
    if name == "manage_window":
        return args.get("action") == "get_work_area"
    return name in {"list_windows", "inspect_ui", "read_screen_text", "find_text",
                    "get_focused_text", "screenshot", "wait"}


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class RemoteBridgeClient:
    """管理到远端活动桌面 守护的 SSH 端口转发隧道与长连接。"""

    def __init__(
        self,
        ssh_target: str,
        remote_root: str = r"C:\ProgramData\RemoteWinMCP",
        confirm_mode: str | None = None,
        allowlist: str | None = None,
        connect_timeout: float = 10.0,
        direct_host_port: tuple[str, int, str] | None = None,
        candidate_release: str | None = None,
    ) -> None:
        self.ssh_target = ssh_target
        self.remote_root = remote_root.rstrip("\\/")
        self.confirm_mode = confirm_mode
        self.allowlist = allowlist
        self.connect_timeout = connect_timeout
        # Optional loopback testing bypass without SSH: (host, port, token)
        self.direct_host_port = direct_host_port
        self.candidate_release = candidate_release

        self.lock = threading.Lock()
        self.tunnel_proc: subprocess.Popen[bytes] | None = None
        self.sock: socket.socket | None = None
        self.reader: Any = None
        self._rpc_id = 1000

    def close(self) -> None:
        with self.lock:
            self._close_unlocked()

    def _close_unlocked(self) -> None:
        if self.reader is not None:
            try:
                self.reader.close()
            except Exception:
                pass
            self.reader = None
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self.tunnel_proc is not None:
            if self.tunnel_proc.poll() is None:
                try:
                    self.tunnel_proc.terminate()
                    self.tunnel_proc.wait(timeout=2.0)
                except Exception:
                    try:
                        self.tunnel_proc.kill()
                    except Exception:
                        pass
            self.tunnel_proc = None

    def _ensure_remote_daemon(self) -> tuple[int, str]:
        command = release_selector(self.remote_root, self.candidate_release)
        command += "& (Join-Path $bundle 'app\\remote\\ensure_daemon.ps1') -BundleRoot $bundle"
        completed = run_remote_ps(self.ssh_target, command, self.connect_timeout)
        stdout = (completed.stdout or "").strip()
        json_line = next((ln.strip() for ln in reversed(stdout.splitlines()) if ln.strip().startswith("{")), "")
        if not json_line or completed.returncode:
            err = (completed.stderr or f"ssh exit={completed.returncode}").strip()
            raise ConnectionError(f"无法连接远端主机 {self.ssh_target}：{err[:300]}")
        info = json.loads(json_line)
        if not info.get("ok"):
            raise ConnectionError(f"远端活动桌面 守护未就绪：{info.get('message') or info}")
        return int(info["port"]), str(info["token"])

    def _connect_unlocked(self) -> None:
        self._close_unlocked()

        if self.direct_host_port is not None:
            host, lport, token = self.direct_host_port
        else:
            rport, token = self._ensure_remote_daemon()
            lport = _free_local_port()
            host = "127.0.0.1"
            self.tunnel_proc = subprocess.Popen(
                [
                    "ssh",
                    "-N",
                    "-o", "BatchMode=yes",
                    "-o", "ExitOnForwardFailure=yes",
                    "-o", "ServerAliveInterval=20",
                    "-o", "ServerAliveCountMax=3",
                    "-o", f"ConnectTimeout={int(self.connect_timeout)}",
                    "-L", f"127.0.0.1:{lport}:127.0.0.1:{rport}",
                    self.ssh_target,
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            # Wait for local forward port to start accepting connections
            deadline = time.monotonic() + self.connect_timeout
            connected = False
            while time.monotonic() < deadline:
                if self.tunnel_proc.poll() is not None:
                    err = (self.tunnel_proc.stderr.read().decode("utf-8", "replace") if self.tunnel_proc.stderr else "").strip()
                    raise ConnectionError(f"SSH 端口转发退出：{err[:300]}")
                try:
                    s = socket.create_connection((host, lport), timeout=0.5)
                    self.sock = s
                    connected = True
                    break
                except OSError:
                    time.sleep(0.15)
            if not connected or self.sock is None:
                self._close_unlocked()
                raise ConnectionError(f"等待本地 SSH 转发端口 {lport} 超时。")

        if self.sock is None:
            self.sock = socket.create_connection((host, lport), timeout=self.connect_timeout)

        self.sock.settimeout(120.0)
        self.reader = self.sock.makefile("rb")

        auth_payload = {"auth": token}
        if self.confirm_mode is not None:
            auth_payload["confirm_mode"] = self.confirm_mode
        if self.allowlist is not None:
            auth_payload["allowlist"] = self.allowlist
        self.sock.sendall((json.dumps(auth_payload) + "\n").encode("utf-8"))
        auth_resp_raw = self.reader.readline(65536)
        if not auth_resp_raw:
            self._close_unlocked()
            raise ConnectionError("远端守护未返回鉴权结果。")
        auth_resp = json.loads(auth_resp_raw.decode("utf-8"))
        if not auth_resp.get("ok") or auth_resp.get("bridge_protocol") != 2:
            self._close_unlocked()
            raise PermissionError(f"远端守护鉴权失败：{auth_resp}")

        # Perform internal MCP initialize handshake on the remote server.py instance
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": core_server.DEFAULT_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "juzi-win-remote-proxy", "version": core_server.VERSION},
            },
        }
        self.sock.sendall((json.dumps(init_req) + "\n").encode("utf-8"))
        init_line = self.reader.readline(core_server.MAX_FRAME_BYTES)
        if not init_line or "result" not in json.loads(init_line):
            self._close_unlocked()
            raise ConnectionError("远端 MCP initialize 握手失败。")
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self.sock.sendall((json.dumps(notif) + "\n").encode("utf-8"))

    def forward_tool_call(self, req_id: Any, params: Any) -> dict[str, Any]:
        with self.lock:
            last_exc: Exception | None = None
            error_code = "remote_unreachable"
            for attempt in range(2):
                sending = False
                try:
                    if self.sock is None or self.reader is None:
                        self._connect_unlocked()
                    assert self.sock is not None and self.reader is not None
                    self._rpc_id += 1
                    wire_req = {"jsonrpc": "2.0", "id": self._rpc_id, "method": "tools/call", "params": params}
                    frame = (json.dumps(wire_req, ensure_ascii=False) + "\n").encode("utf-8")
                    sending = True  # sendall may fail after sending part or all of the frame.
                    self.sock.sendall(frame)
                    resp_raw = self.reader.readline(16 * 1024 * 1024)
                    if not resp_raw:
                        raise ConnectionError("远端连接已断开（EOF）。")
                    resp = json.loads(resp_raw.decode("utf-8"))
                    if not isinstance(resp, dict) or resp.get("id") != self._rpc_id:
                        raise ConnectionError("远端响应与本次请求不匹配。")
                    resp["id"] = req_id
                    return resp
                except Exception as exc:
                    last_exc = exc
                    self._close_unlocked()
                    if sending and not _retryable_read(params):
                        error_code = "remote_outcome_unknown"
                        break
                    if attempt == 0:
                        continue
            err_payload = {
                "ok": False,
                "error": error_code,
                "error_code": error_code,
                "ssh_target": self.ssh_target,
                "message": ("执行结果未知，请先核对远端状态。" if error_code == "remote_outcome_unknown" else "") + str(last_exc),
            }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(err_payload, ensure_ascii=False, indent=2)}],
                    "isError": True,
                },
            }


def serve_proxy(bridge: RemoteBridgeClient, server_name: str) -> int:
    state: dict[str, Any] = {"initialized": False, "protocol": None, "cancel_requested": False}
    try:
        while True:
            raw = sys.stdin.buffer.readline(core_server.MAX_FRAME_BYTES + 1)
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                message = core_server._parse_frame(line)
            except Exception as exc:
                resp = core_server._jsonrpc_error(None, -32700, f"Parse error: {exc}")
                sys.stdout.write(json.dumps(resp, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
                continue

            if not isinstance(message, dict):
                resp = core_server._jsonrpc_error(None, -32600, "Invalid Request")
                sys.stdout.write(json.dumps(resp, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
                continue

            method = message.get("method")
            req_id = message.get("id")

            # Intercept tools/call after initialization -> lazy forward to remote PC!
            if state.get("initialized") and method == "tools/call" and "id" in message:
                resp = bridge.forward_tool_call(req_id, message.get("params"))
            else:
                resp = core_server._handle(message, state)
                if method == "initialize" and isinstance(resp, dict) and "result" in resp:
                    resp["result"]["serverInfo"]["name"] = server_name
                    resp["result"]["instructions"] = (
                        f"[远程电脑控制 target={bridge.ssh_target}] " + resp["result"].get("instructions", "")
                    )

            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False, separators=(",", ":")) + "\n")
                sys.stdout.flush()
    finally:
        bridge.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Local MCP stdio lazy proxy for remote juzi-win-dsh over SSH")
    parser.add_argument("--ssh-target", default=os.environ.get("JUZI_WIN_REMOTE_SSH_TARGET", "friend-pc"))
    parser.add_argument("--remote-root", default=os.environ.get("JUZI_WIN_REMOTE_ROOT", r"C:\ProgramData\RemoteWinMCP"))
    parser.add_argument("--server-name", default=os.environ.get("JUZI_WIN_REMOTE_SERVER_NAME", "friend_win"))
    parser.add_argument("--confirm-mode", choices=("always", "allowlist", "off"), default=os.environ.get("JUZI_WIN_DSH_CONFIRM_MODE"))
    parser.add_argument("--allowlist", default=os.environ.get("JUZI_WIN_DSH_ALLOWLIST"))
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    args = parser.parse_args()

    bridge = RemoteBridgeClient(
        ssh_target=args.ssh_target,
        remote_root=args.remote_root,
        confirm_mode=args.confirm_mode,
        allowlist=args.allowlist,
        connect_timeout=args.connect_timeout,
    )
    return serve_proxy(bridge, args.server_name)


if __name__ == "__main__":
    raise SystemExit(main())
