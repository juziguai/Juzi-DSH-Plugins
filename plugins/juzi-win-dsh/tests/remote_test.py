#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`remote/` 模块隔离回归与本机回环集成测试（纯标准库 unittest）。

验证范围：
1. 离线零阻塞启动：远端不可达时，`local_proxy` 毫秒级响应 `initialize` / `ping` / `tools/list`（完整 21 工具）。
2. 回环鉴权边界：`Session1Daemon` 仅绑定 `127.0.0.1`，拒绝非法 JSON 首帧与错误 Token。
3. 端到端转发与连接复用：`local_proxy` -> `Session1Daemon` -> `server.py` 连续调用只读工具并复用同一长连接。
4. 断线/不可达错误封装：远端端口不可达时返回结构化 `error_code="remote_unreachable"` 且 `isError=True`。
5. 空闲自动回收：无活跃连接达到 `idle_timeout` 后自动退出并清理 `daemon_state.json`。
6. 归档打包过滤：`sync_release.pack_bundle_zip` 正确打包便携包并排除缓存与 `runtime/` 状态目录。
"""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PLUGIN_ROOT / "src"
REMOTE_DIR = PLUGIN_ROOT / "remote"
for p in (SRC_DIR, REMOTE_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import local_proxy  # noqa: E402
import session1_daemon  # noqa: E402
import sync_release  # noqa: E402


def _wait_for_file(path: Path, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        time.sleep(0.05)
    raise TimeoutError(f"State file did not appear in time: {path}")


class _FakeStdio:
    def __init__(self, lines: list[dict]) -> None:
        raw = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in lines).encode("utf-8")
        self.buffer = io.BytesIO(raw)


class RemoteBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = PLUGIN_ROOT / f".tmp-remote-test-{int(time.time() * 1000)}-{id(self)}"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_proxy_offline_startup_and_tool_list_zero_ssh(self) -> None:
        bridge = local_proxy.RemoteBridgeClient(
            ssh_target="offline-nonexistent-host.invalid",
            connect_timeout=1.0,
        )
        requests = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "ping"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        ]
        out = io.StringIO()
        with mock.patch("subprocess.run", side_effect=AssertionError("Offline metadata must not invoke ssh")), \
             mock.patch("subprocess.Popen", side_effect=AssertionError("Offline metadata must not spawn tunnel")), \
             mock.patch.object(sys, "stdin", _FakeStdio(requests)), \
             mock.patch.object(sys, "stdout", out):
            rc = local_proxy.serve_proxy(bridge, server_name="friend_win")

        self.assertEqual(rc, 0)
        frames = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
        self.assertEqual(len(frames), 3)
        self.assertEqual(frames[0]["id"], 1)
        self.assertEqual(frames[0]["result"]["serverInfo"]["name"], "friend_win")
        self.assertIn("target=offline-nonexistent-host.invalid", frames[0]["result"]["instructions"])
        self.assertEqual(frames[1]["id"], 2)
        tools = frames[2]["result"]["tools"]
        self.assertEqual(len(tools), 21)

    def test_daemon_loopback_auth_and_end_to_end_forwarding(self) -> None:
        state_file = self.tmp_dir / "private" / "daemon_state.json"
        daemon = session1_daemon.Session1Daemon(
            server_py=PLUGIN_ROOT / "server.py",
            state_file=state_file,
            port=0,
            idle_timeout=30.0,
            confirm_mode="off",
        )
        t = threading.Thread(target=daemon.serve, daemon=True)
        t.start()
        try:
            state = _wait_for_file(state_file)
            self.assertEqual(state["host"], "127.0.0.1")
            port = int(state["port"])
            token = str(state["token"])
            self.assertGreater(port, 0)
            self.assertEqual(len(token), 64)

            # 1. Invalid JSON first frame must be rejected
            with socket.create_connection(("127.0.0.1", port), timeout=3.0) as s:
                s.sendall(b"not-json\n")
                with s.makefile("rb") as r:
                    resp = json.loads(r.readline().decode("utf-8"))
                self.assertFalse(resp["ok"])
                self.assertEqual(resp["error"], "invalid_auth_json")

            # 2. Wrong token must be rejected
            with socket.create_connection(("127.0.0.1", port), timeout=3.0) as s:
                s.sendall(b'{"auth":"wrong_token"}\n')
                with s.makefile("rb") as r:
                    resp = json.loads(r.readline().decode("utf-8"))
                self.assertFalse(resp["ok"])
                self.assertEqual(resp["error"], "unauthorized")

            # 3. Valid token via RemoteBridgeClient + serve_proxy end-to-end read-only calls
            bridge = local_proxy.RemoteBridgeClient(
                ssh_target="loopback-test",
                confirm_mode="off",
                direct_host_port=("127.0.0.1", port, token),
            )
            requests = [
                {
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
                },
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {"name": "manage_window", "arguments": {"action": "get_work_area"}},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 12,
                    "method": "tools/call",
                    "params": {"name": "wait", "arguments": {"condition": "timeout", "timeout_ms": 5}},
                },
            ]

            first_sock_id: int | None = None
            orig_forward = bridge.forward_tool_call

            def tracked_forward(req_id, params):
                nonlocal first_sock_id
                res = orig_forward(req_id, params)
                if first_sock_id is None and bridge.sock is not None:
                    first_sock_id = id(bridge.sock)
                elif bridge.sock is not None:
                    self.assertEqual(id(bridge.sock), first_sock_id, "Warm socket should be reused across calls")
                return res

            out = io.StringIO()
            with mock.patch.object(bridge, "forward_tool_call", side_effect=tracked_forward), \
                 mock.patch.object(sys, "stdin", _FakeStdio(requests)), \
                 mock.patch.object(sys, "stdout", out):
                local_proxy.serve_proxy(bridge, server_name="loopback_win")

            frames = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
            self.assertEqual([f["id"] for f in frames], [10, 11, 12])

            work_area_payload = json.loads(frames[1]["result"]["content"][0]["text"])
            self.assertTrue(work_area_payload["ok"])
            self.assertGreater(work_area_payload["screen"]["width"], 0)
            self.assertGreaterEqual(work_area_payload["count"], 1)

            wait_payload = json.loads(frames[2]["result"]["content"][0]["text"])
            self.assertTrue(wait_payload["ok"])
        finally:
            daemon.stop_event.set()
            t.join(timeout=5.0)

    def test_unreachable_remote_returns_structured_error(self) -> None:
        # Grab an unused port and immediately close it so connection fails fast
        closed_port = local_proxy._free_local_port()
        bridge = local_proxy.RemoteBridgeClient(
            ssh_target="unreachable-box",
            connect_timeout=0.5,
            direct_host_port=("127.0.0.1", closed_port, "dummy"),
        )
        try:
            resp = bridge.forward_tool_call(99, {"name": "system", "arguments": {}})
            self.assertEqual(resp["id"], 99)
            self.assertTrue(resp["result"]["isError"])
            payload = json.loads(resp["result"]["content"][0]["text"])
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error_code"], "remote_unreachable")
            self.assertEqual(payload["ssh_target"], "unreachable-box")
        finally:
            bridge.close()

    def test_lost_response_only_replays_reads(self) -> None:
        for name, action, count in (("type_text", None, 1), ("action_batch", None, 1),
                                    ("manage_window", "maximize", 1), ("unknown", None, 1),
                                    ("manage_window", "get_work_area", 2), ("wait", None, 2)):
            with self.subTest(name=name, action=action):
                bridge = local_proxy.RemoteBridgeClient("test")
                sent = []

                def connect():
                    bridge.sock = mock.Mock()
                    bridge.sock.sendall.side_effect = lambda frame: sent.append(json.loads(frame))
                    reply = {"jsonrpc": "2.0", "id": 1002, "result": {"isError": False}}
                    bridge.reader = io.BytesIO(json.dumps(reply).encode() if sent else b"")

                with mock.patch.object(bridge, "_connect_unlocked", side_effect=connect):
                    result = bridge.forward_tool_call(100, {"name": name, "arguments": {"action": action}})["result"]
                self.assertEqual(len(sent), count)
                if count == 1:
                    self.assertEqual(json.loads(result["content"][0]["text"])["error_code"], "remote_outcome_unknown")
                else:
                    self.assertFalse(result["isError"])
                bridge.close()

    def test_confirmation_policy_only_tightens(self) -> None:
        policy = session1_daemon._session_policy
        self.assertEqual(policy("always", "", {"confirm_mode": "off"}), ("always", ""))
        self.assertEqual(policy("allowlist", "EDIT.exe;other", {}), ("allowlist", "edit;other"))
        self.assertEqual(policy("allowlist", "edit", {"confirm_mode": "allowlist", "allowlist": "extra;EDIT.EXE"}),
                         ("allowlist", "edit"))
        self.assertEqual(policy("off", "", {"confirm_mode": "always"}), ("always", ""))
        self.assertEqual(policy("off", "", {"confirm_mode": "invalid"}), ("always", ""))

    def test_desktop_session_must_match_and_stay_active(self) -> None:
        state_file = self.tmp_dir / "private" / "state.json"
        options = dict(server_py=PLUGIN_ROOT / "server.py", state_file=state_file)
        with self.assertRaises(RuntimeError):
            session1_daemon.Session1Daemon(**options, expected_session=-1)
        daemon = session1_daemon.Session1Daemon(**options)
        t = threading.Thread(target=daemon.serve, daemon=True)
        t.start()
        try:
            state = _wait_for_file(state_file)
            with socket.create_connection(("127.0.0.1", state["port"]), timeout=5) as sock, sock.makefile("rb") as reply:
                sock.sendall((json.dumps({"auth": state["token"]}) + "\n").encode())
                self.assertTrue(json.loads(reply.readline())["ok"])
                with mock.patch.object(session1_daemon.desktop_session, "is_active", return_value=False):
                    sock.sendall(b'{"jsonrpc":"2.0","id":1,"method":"ping"}\n')
                    self.assertEqual(reply.readline(), b"")
        finally:
            daemon.stop_event.set()
            t.join(5)

    def test_private_directory_acl_exists_before_publication(self) -> None:
        private = self.tmp_dir / "private"
        # Create a dedicated state directory, then verify its file inheritance.
        subprocess.run(["powershell.exe", "-NoProfile", "-File", str(REMOTE_DIR / "private_state.ps1"),
                        "-Directory", str(private)], check=True, capture_output=True)
        sample = private / "sample"
        sample.write_text("test")
        check = ("$a=[IO.File]::GetAccessControl($env:JUZI_ACL_SAMPLE); "
                 "$a.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | "
                 "ForEach-Object {$_.IdentityReference.Value}")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", check], check=True,
                                capture_output=True, text=True, env={**os.environ, "JUZI_ACL_SAMPLE": str(sample)})
        self.assertIn("S-1-5-18", result.stdout.splitlines())
        self.assertNotIn("S-1-5-32-545", result.stdout.splitlines())
        self.assertNotIn("S-1-5-11", result.stdout.splitlines())
        # Refuse a pre-existing directory with inherited permissions.
        refused = subprocess.run(["powershell.exe", "-NoProfile", "-File", str(REMOTE_DIR / "private_state.ps1"),
                                  "-Directory", str(self.tmp_dir)], capture_output=True)
        self.assertNotEqual(refused.returncode, 0)

    def test_failed_bridge_verification_cannot_publish(self) -> None:
        archive = self.tmp_dir / "candidate.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("VERSION.json", json.dumps({"bridge_protocol": 2, "verified_server": {"version": "test"},
                                                   "verified_tools": 21}))
        ok = subprocess.CompletedProcess([], 0, "", "")
        checked = subprocess.CompletedProcess([], 0, '{"server_info":{"version":"test"},"tool_count":21}', "")
        with mock.patch.object(sync_release, "run_remote_ps", side_effect=[ok, checked]) as remote, \
             mock.patch.object(subprocess, "run", return_value=ok), \
             mock.patch.object(local_proxy.RemoteBridgeClient, "forward_tool_call", return_value={
                 "result": {"isError": True, "content": [{"text": '{"ok":false,"error_code":"test_failure"}'}]}}):
            result = sync_release.sync_to_host("test", archive, r"C:\fixture", verify_bridge=True)
        self.assertFalse(result["ok"])
        self.assertFalse(result["bridge_verified"])
        self.assertEqual(result["error"], "test_failure")
        self.assertFalse(any("Publish-Release" in call.args[1] for call in remote.call_args_list))
        with mock.patch.object(sys, "argv", ["sync_release", "--skip-build", "--verify-bridge", "--ssh-target", "test"]), \
             mock.patch.object(sync_release, "pack_bundle_zip", return_value=0), \
             mock.patch.object(sync_release, "sync_to_host", return_value=result), \
             mock.patch.object(sys, "stdout", io.StringIO()):
            self.assertNotEqual(sync_release.main(), 0)

    def test_release_switch_preserves_previous_directory(self) -> None:
        # Exercise the same Windows PowerShell filesystem operations as the installer.
        root = self.tmp_dir / "install with spaces"
        script = """
$ErrorActionPreference='Stop'
. $env:JUZI_STORE_SCRIPT
$store=Open-ReleaseStore $env:JUZI_TEST_ROOT -Create
$first='1' * 32
$next='2' * 32
$old=Join-Path $store $first
[IO.Directory]::CreateDirectory($old) | Out-Null
[IO.Directory]::CreateDirectory((Join-Path $store $next)) | Out-Null
Publish-Release $store $first
$marker=Join-Path $store 'active-release'
if ([IO.File]::ReadAllText($marker) -ne $first) { throw 'initial publish failed' }
Publish-Release $store $next
if ([IO.File]::ReadAllText($marker) -ne $next -or -not [IO.Directory]::Exists($old)) { throw 'switch failed' }
"""
        subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                       capture_output=True, env={**os.environ, "JUZI_TEST_ROOT": str(root),
                                                 "JUZI_STORE_SCRIPT": str(REMOTE_DIR / "release_store.ps1")})

    def test_daemon_idle_timeout_exits_and_removes_state_file(self) -> None:
        state_file = self.tmp_dir / "private" / "idle_state.json"
        daemon = session1_daemon.Session1Daemon(
            server_py=PLUGIN_ROOT / "server.py",
            state_file=state_file,
            port=0,
            idle_timeout=10.0,
        )
        # Shorten timeout on instance for fast unit test
        daemon.idle_timeout = 0.2
        t = threading.Thread(target=daemon.serve, daemon=True)
        t.start()
        _wait_for_file(state_file)
        t.join(timeout=4.0)
        self.assertFalse(t.is_alive(), "Daemon should auto-exit after idle_timeout")
        self.assertFalse(state_file.exists(), "State file should be unlinked upon clean exit")

    def test_sync_release_pack_bundle_excludes_runtime_and_cache(self) -> None:
        fake_bundle = self.tmp_dir / "bundle"
        (fake_bundle / "python").mkdir(parents=True)
        (fake_bundle / "app" / "__pycache__").mkdir(parents=True)
        (fake_bundle / "runtime").mkdir(parents=True)
        (fake_bundle / "VERSION.json").write_text('{"python":"3.14"}', encoding="utf-8")
        (fake_bundle / "python" / "python.exe").write_bytes(b"MZ-fake")
        (fake_bundle / "app" / "server.py").write_text("# entry\n", encoding="utf-8")
        (fake_bundle / "app" / "__pycache__" / "x.pyc").write_bytes(b"pyc")
        (fake_bundle / "runtime" / "daemon_state.json").write_text("{}", encoding="utf-8")

        out_zip = self.tmp_dir / ".tmp-bundle.zip"
        size_mb = sync_release.pack_bundle_zip(fake_bundle, out_zip)
        self.assertGreaterEqual(size_mb, 0.0)
        with zipfile.ZipFile(out_zip, "r") as zf:
            names = set(zf.namelist())
        self.assertIn("VERSION.json", names)
        self.assertIn("python/python.exe", names)
        self.assertIn("app/server.py", names)
        self.assertFalse(any("runtime" in n or "__pycache__" in n or n.endswith(".pyc") for n in names))


if __name__ == "__main__":
    unittest.main(verbosity=2)
