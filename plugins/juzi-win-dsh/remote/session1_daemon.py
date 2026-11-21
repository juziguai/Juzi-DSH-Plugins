#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""远端交互桌面本地回环 MCP 守护桥。

安全与设计边界：
1. 强制仅绑定 127.0.0.1（拒绝绑定非回环地址），绝不向局域网或虚拟网卡直接暴露端口。
2. 启动时生成本进程有效的 256-bit 随机 token，受限状态目录在写入前校验。
3. 每个通过鉴权的连接派生独立 `server.py` 子进程桥接 stdio，100% 复用原版 21 个工具与常驻 STA Worker；
   连接断开即向子进程发送 EOF，自动回收全部辅助进程。
4. 默认空闲 900 秒无活跃连接自动退出，平时 0 内存常驻。
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import desktop_session


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    fd, temp_name = tempfile.mkstemp(dir=path.parent)
    tmp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _session_policy(host_mode, host_allow, request):
    """Intersect confirmation exemptions; an omitted client setting inherits the host."""
    levels = ("off", "allowlist", "always")
    client_mode = request.get("confirm_mode", "allowlist" if "allowlist" in request else "off")
    if client_mode not in levels or host_mode not in levels:
        return "always", ""
    mode = levels[max(levels.index(host_mode), levels.index(client_mode))]
    if mode != "allowlist":
        return mode, ""

    def names(value):
        if not isinstance(value, str):
            return set()
        return {n.strip().lower().removesuffix(".exe") for n in value.split(";") if n.strip()}

    allowed = names(host_allow) if host_mode == "allowlist" else names(request.get("allowlist"))
    if client_mode == "allowlist" or "allowlist" in request:
        allowed &= names(request.get("allowlist"))
    return mode, ";".join(sorted(allowed))


class Session1Daemon:
    def __init__(
        self,
        server_py: Path,
        state_file: Path,
        port: int = 0,
        idle_timeout: float = 900.0,
        confirm_mode: str = "always",
        allowlist: str = "",
        expected_session: int | None = None,
    ) -> None:
        self.server_py = server_py.resolve()
        self.state_file = state_file.absolute()
        self.req_port = port
        self.idle_timeout = max(10.0, float(idle_timeout))
        self.confirm_mode = confirm_mode
        self.allowlist = allowlist
        self.session_id = desktop_session.current_session()
        if expected_session is not None and expected_session != self.session_id:
            raise RuntimeError("守护进程不在指定桌面会话中。")
        self.token = secrets.token_hex(32)
        self.active_clients = 0
        self.last_activity = time.monotonic()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.sock: socket.socket | None = None

    def _touch(self) -> None:
        with self.lock:
            self.last_activity = time.monotonic()

    def _handle_client(self, conn: socket.socket) -> None:
        with self.lock:
            self.active_clients += 1
            self.last_activity = time.monotonic()

        proc: subprocess.Popen[bytes] | None = None
        reader: Any = None
        try:
            conn.settimeout(8.0)
            reader = conn.makefile("rb")
            auth_line = reader.readline(4096)
            if not auth_line:
                return
            try:
                auth_obj = json.loads(auth_line.decode("utf-8"))
            except Exception:
                conn.sendall(b'{"ok":false,"error":"invalid_auth_json"}\n')
                return

            supplied = str(auth_obj.get("auth", "")) if isinstance(auth_obj, dict) else ""
            if not hmac.compare_digest(supplied, self.token):
                conn.sendall(b'{"ok":false,"error":"unauthorized"}\n')
                return

            if not desktop_session.is_active(self.session_id):
                conn.sendall(b'{"ok":false,"error":"inactive_session"}\n')
                return
            req_mode, req_allow = _session_policy(self.confirm_mode, self.allowlist, auth_obj)

            env = {
                **os.environ,
                "JUZI_WIN_DSH_CONFIRM_MODE": req_mode,
                "JUZI_WIN_DSH_ALLOWLIST": req_allow,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
            }
            proc = subprocess.Popen(
                [sys.executable, "-u", str(self.server_py)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=tempfile.gettempdir(),
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            conn.settimeout(None)
            conn.sendall(b'{"ok":true,"bridge_protocol":2}\n')

            def pump_stdout() -> None:
                assert proc is not None and proc.stdout is not None
                try:
                    while True:
                        line = proc.stdout.readline()
                        if not line:
                            break
                        self._touch()
                        conn.sendall(line)
                except OSError:
                    pass
                finally:
                    try:
                        conn.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass

            t_out = threading.Thread(target=pump_stdout, daemon=True)
            t_out.start()

            assert proc.stdin is not None
            try:
                while not self.stop_event.is_set():
                    line = reader.readline(2 * 1024 * 1024)
                    if not line:
                        break
                    if not desktop_session.is_active(self.session_id):
                        break
                    self._touch()
                    proc.stdin.write(line)
                    proc.stdin.flush()
            except OSError:
                pass
            finally:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
                t_out.join(timeout=5.0)
        finally:
            if reader is not None:
                try:
                    reader.close()
                except OSError:
                    pass
            if proc is not None:
                if proc.poll() is None:
                    try:
                        proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1.0)
                if proc.stdout is not None:
                    try:
                        proc.stdout.close()
                    except OSError:
                        pass
            try:
                conn.close()
            except OSError:
                pass
            with self.lock:
                self.active_clients = max(0, self.active_clients - 1)
                self.last_activity = time.monotonic()

    def serve(self) -> int:
        if not self.server_py.is_file():
            raise FileNotFoundError(f"server.py not found: {self.server_py}")
        if not desktop_session.is_active(self.session_id):
            raise RuntimeError("目标桌面会话未处于活动状态。")
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-File",
                        str(Path(__file__).with_name("private_state.ps1")), "-Directory", str(self.state_file.parent)],
                       check=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # Strictly loopback only!
        srv.bind(("127.0.0.1", self.req_port))
        srv.listen(8)
        srv.settimeout(1.0)
        self.sock = srv
        actual_port = srv.getsockname()[1]

        state = {
            "pid": os.getpid(),
            "session_id": self.session_id,
            "confirm_mode": self.confirm_mode,
            "allowlist": self.allowlist,
            "host": "127.0.0.1",
            "port": actual_port,
            "token": self.token,
            "started_at": time.time(),
            "idle_timeout": self.idle_timeout,
        }
        try:
            _atomic_write_json(self.state_file, state)
            while not self.stop_event.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    with self.lock:
                        idle_for = time.monotonic() - self.last_activity
                        busy = self.active_clients > 0
                    if (not busy) and idle_for >= self.idle_timeout:
                        break
                    continue
                except OSError:
                    break

                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
        finally:
            try:
                srv.close()
            except OSError:
                pass
            try:
                if self.state_file.is_file():
                    cur = json.loads(self.state_file.read_text(encoding="utf-8"))
                    if cur.get("pid") == os.getpid():
                        self.state_file.unlink(missing_ok=True)
            except Exception:
                pass
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive desktop loopback daemon for juzi-win-dsh")
    default_server = Path(__file__).resolve().parent.parent / "server.py"
    default_state = Path(os.environ["LOCALAPPDATA"]) / f"JuziWinDSH-State-{desktop_session.current_session()}" / "daemon_state.json"
    parser.add_argument("--server-py", type=Path, default=default_server)
    parser.add_argument("--state-file", type=Path, default=default_state)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--idle-timeout", type=float, default=900.0)
    parser.add_argument("--confirm-mode", choices=("always", "allowlist", "off"), default="always")
    parser.add_argument("--allowlist", type=str, default="")
    parser.add_argument("--expected-session", type=int)
    args = parser.parse_args()

    daemon = Session1Daemon(
        server_py=args.server_py,
        state_file=args.state_file,
        port=args.port,
        idle_timeout=args.idle_timeout,
        confirm_mode=args.confirm_mode,
        allowlist=args.allowlist,
        expected_session=args.expected_session,
    )
    return daemon.serve()


if __name__ == "__main__":
    raise SystemExit(main())
