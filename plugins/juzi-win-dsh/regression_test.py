#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1.1.0 回归测试（纯标准库 unittest；不执行真实键鼠/窗口/剪贴板写）。

覆盖 Codex 审查 R1-R13 中可隔离验证的行为：
R2 目标核对、R3 schema 类型、R4 剪贴板事务、R5 解析限制、R6 system 确认、
R7 禁止清单/启动器、R8 截图尺寸契约、R9 协议生命周期、R10 isError、R12/R13 契约。
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import clipboard_win  # noqa: E402
import launcher  # noqa: E402
import schema_validate  # noqa: E402
import security  # noqa: E402
import server  # noqa: E402
import winapi  # noqa: E402


def _window(hwnd=1, process="notepad.exe", title="Notepad"):
    return {
        "hwnd": hwnd, "process": process, "pid": hwnd, "title": title,
        "class": "TestWindow", "rect": {"x": 0, "y": 0, "width": 100, "height": 100},
        "minimized": False, "maximized": False, "foreground": True, "tool_window": False,
    }


class RegressionTests(unittest.TestCase):
    def test_r2_click_hwnd_must_match_actual_target(self):
        actual = _window(2, "bitwarden.exe", "Vault")
        with mock.patch.object(winapi, "resolve_click_point", return_value=(50, 50)), \
             mock.patch.object(winapi, "window_at_point", return_value=actual), \
             mock.patch.object(winapi, "click") as dispatched:
            result = json.loads(server.click(10, 10, hwnd=1))
        self.assertEqual(result["error"], "target_mismatch")
        dispatched.assert_not_called()

    def test_r2_drag_aborts_without_hold_delay(self):
        allowed = _window(1)
        bad = _window(2, "1password.exe", "Vault")
        calls = []

        def target_at(*_args):
            calls.append(1)
            return allowed if len(calls) == 1 else bad

        sleeps = []
        events = []
        with mock.patch.object(winapi, "resolve_click_point", side_effect=[(0, 0), (100, 100)]), \
             mock.patch.object(winapi, "window_at_point", side_effect=target_at), \
             mock.patch.object(winapi, "_mouse_event", side_effect=lambda *args, **kwargs: events.append(args)), \
             mock.patch.object(time, "sleep", side_effect=lambda seconds: sleeps.append(seconds)):
            result = winapi.drag(0, 0, 100, 100, hold_ms_after=5000)
        self.assertTrue(result["aborted_blocked_window"])
        self.assertNotIn(5.0, sleeps)
        self.assertEqual([event[0] for event in events], [0x0002, 0x0004])

    def test_r3_schema_rejects_wrong_types_and_unknown_fields(self):
        cases = [
            ("click", {"x": 1, "y": 2, "double": "false"}),
            ("click", {"x": 1.5, "y": 2}),
            ("system", {"lock": "false"}),
            ("click", {"x": 1, "y": 2, "bogus": 1}),
            ("list_windows", {"include_tool_windows": "false"}),
        ]
        for name, args in cases:
            result = server._call_tool(name, args)
            self.assertTrue(result["isError"], (name, args))
            payload = json.loads(result["content"][0]["text"])
            self.assertEqual(payload["error_code"], "invalid_arguments")
        self.assertTrue(schema_validate.validate(
            {"type": "number"}, float("nan")
        ))

    def test_r4_clipboard_conflict_does_not_overwrite(self):
        clipboard_win._backup = {
            "snapshot": {"status": "success", "text": "old", "sequence": 10},
            "owned_sequence": 10,
            "at": 0,
        }
        with mock.patch.object(clipboard_win, "_sequence", return_value=11), \
             mock.patch.object(clipboard_win, "_write_unlocked") as write:
            result = clipboard_win.restore()
        self.assertFalse(result["restored"])
        self.assertTrue(result["conflict"])
        write.assert_not_called()
        clipboard_win._backup = None

    def test_r4_backup_failure_does_not_write(self):
        with mock.patch.object(clipboard_win, "_snapshot_unlocked", side_effect=clipboard_win.ClipboardError("备份失败")), \
             mock.patch.object(clipboard_win, "_write_unlocked") as write:
            with self.assertRaises(clipboard_win.ClipboardError):
                clipboard_win.set_text("new", backup=True)
        write.assert_not_called()

    def test_r5_parser_limits(self):
        with self.assertRaises(ValueError):
            server._parse_frame('{"x":' + "9" * 5000 + "}")
        with self.assertRaises(ValueError):
            server._parse_frame("[" * 500 + "0" + "]" * 500)
        with self.assertRaises(ValueError):
            server._parse_frame("NaN")

    def test_r6_system_write_requires_confirmation(self):
        server.GATE.mode = "always"
        with mock.patch.object(server.system_control, "apply_system") as apply:
            result = json.loads(server.system(lock=True))
        self.assertEqual(result["status"], "confirmation_required")
        apply.assert_not_called()
        server.GATE.mode = "off"

    def test_r7_forbidden_identity_and_password_managers(self):
        self.assertIsNotNone(security.forbidden_reason({"process": "", "title": "x"}))
        for info in (
            {"process": "ProtonPass.exe", "title": "Vault"},
            {"process": "Enpass.exe", "title": "Vault"},
            {"process": "chrome.exe", "title": "Google 密码管理工具"},
            {"process": "firefox.exe", "title": "密码 — Mozilla Firefox"},
        ):
            self.assertIsNotNone(security.forbidden_reason(info), info)

    def test_r7_launcher_rejects_canonicalized_script_host(self):
        with self.assertRaises(PermissionError):
            launcher._validate_path(r"C:\Windows\System32\cmd.exe.")
        with self.assertRaises(PermissionError):
            launcher._validate_path(r"C:\Windows\System32\cmd.exe ")

    def test_r8_capture_rejects_mismatched_client_size(self):
        from PIL import Image

        fake_info = _window(1)
        fake_image = Image.new("RGB", (800, 600), "white")
        with mock.patch.object(winapi, "window_info", return_value=fake_info), \
             mock.patch.object(winapi, "client_metrics", return_value={"x": 0, "y": 0, "width": 984, "height": 761}), \
             mock.patch("PIL.ImageGrab.grab", return_value=fake_image):
            with self.assertRaises(ValueError):
                winapi.capture(max_width=0, hwnd=1)

    def test_r9_protocol_lifecycle(self):
        state = {"initialized": False, "protocol": None, "cancel_requested": False}
        response = server._handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}, state)
        self.assertEqual(response["error"]["code"], -32002)
        response = server._handle(
            {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2099-99-99"}},
            state,
        )
        self.assertEqual(response["result"]["protocolVersion"], server.DEFAULT_PROTOCOL_VERSION)
        response = server._handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": []}, state)
        self.assertEqual(response["error"]["code"], -32602)

    def test_r10_iserror_and_pending(self):
        failed = server._call_tool("type_text", {"text": ""})
        self.assertTrue(failed["isError"])
        server.GATE.mode = "always"
        pending = server._call_tool("click", {"x": 1, "y": 2})
        payload = json.loads(pending["content"][0]["text"])
        self.assertFalse(pending["isError"])
        self.assertEqual(payload["status"], "confirmation_required")
        server.GATE.mode = "off"
        timeout = server._call_tool("wait", {
            "condition": "window_exists", "title": "绝对不存在的窗口标题ZZZ",
            "timeout_ms": 60, "poll_ms": 50,
        })
        payload = json.loads(timeout["content"][0]["text"])
        self.assertFalse(timeout["isError"])
        self.assertTrue(payload["timed_out"])

    def test_r12_paste_uses_stdin_not_argv(self):
        source = (ROOT / "paste_text.py").read_text(encoding="utf-8")
        self.assertNotIn("-TextB64", source)
        self.assertIn("input=text", source)

    def test_r13_pillow_minimum(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("Pillow>=11.2.1", requirements)


if __name__ == "__main__":
    unittest.main(verbosity=2)
