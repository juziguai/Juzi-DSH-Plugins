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
import subprocess
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
    def test_batch_stops_after_unverified_input(self):
        focus = {"ok": False, "focus_id": "1", "error": "focused_text_unavailable"}
        actions = [{"tool": "type_text", "arguments": {"text": "hello", "allow_unverified": True}},
                   {"tool": "press_keys", "arguments": {"keys": "enter"}}]
        with mock.patch.object(server, "GATE", server.ConfirmationGate("always", [])), \
             mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(winapi, "focused_hwnd", return_value=10), \
             mock.patch.object(server.focused_text, "read", return_value=focus), \
             mock.patch.object(server, "paste_text", return_value={"paste_ok": True}) as paste, \
             mock.patch.object(winapi, "press_keys") as keys:
            pending = json.loads(server.input_batch(1, actions))
            result = json.loads(server.input_batch(1, actions, pending["confirm_token"]))
        self.assertEqual(result["error"], "batch_stopped")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(paste.call_count, 1)
        keys.assert_not_called()

    def test_unverified_option_is_bound_to_confirmation(self):
        focus = {"ok": True, "editable": True, "focus_id": "1", "text": ""}
        with mock.patch.object(server, "GATE", server.ConfirmationGate("always", [])), \
             mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(server.focused_text, "read", return_value=focus), \
             mock.patch.object(server, "paste_text") as paste:
            pending = json.loads(server.type_text("hello"))
            result = json.loads(server.type_text("hello", confirm_token=pending["confirm_token"], allow_unverified=True))
        self.assertEqual(result["error"], "invalid_confirm_token")
        paste.assert_not_called()

    def test_soft_line_breaks_normalize_without_losing_content(self):
        match = server.focused_text.insertion_matches
        self.assertTrue(match("\r", "第一行\v第二行\r", "第一行\n第二行"))
        self.assertFalse(match("", "第一行\v错误", "第一行\n第二行"))

    def test_verification_retries_reads_without_dispatch(self):
        before = {"ok": True, "focus_id": "1", "text": ""}
        with mock.patch.object(server.focused_text, "read", side_effect=[before, before, {**before, "text": "迟到"}]) as read, \
             mock.patch.object(server.focused_text.time, "sleep"):
            verified, reason = server.focused_text.verify_insertion(1, before, "迟到")
        self.assertTrue(verified)
        self.assertIsNone(reason)
        self.assertEqual(read.call_count, 3)

    def test_verification_stops_on_changed_focus(self):
        before = {"ok": True, "focus_id": "1", "text": ""}
        with mock.patch.object(server.focused_text, "read", return_value={**before, "focus_id": "2", "text": "hello"}) as read:
            verified, reason = server.focused_text.verify_insertion(1, before, "hello")
        self.assertFalse(verified)
        self.assertEqual(reason, "target_changed")
        self.assertEqual(read.call_count, 1)

    def test_explicit_unverified_dispatch_and_strict_rejection(self):
        unreadable = {"ok": False, "focus_id": "1", "error": "focused_text_unavailable"}
        with mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(server, "_gate", return_value=None), \
             mock.patch.object(server.focused_text, "read", return_value=unreadable), \
             mock.patch.object(server, "paste_text", return_value={"paste_ok": True}) as paste:
            strict = json.loads(server.type_text("hello", hwnd=1))
            self.assertFalse(strict["ok"])
            paste.assert_not_called()
            relaxed = json.loads(server.type_text("hello", hwnd=1, allow_unverified=True))
        self.assertTrue(relaxed["ok"])
        self.assertFalse(relaxed["verified"])
        self.assertFalse(relaxed["paste_ok"])
        self.assertEqual(relaxed["status"], "dispatched_unverified")
        self.assertEqual(paste.call_count, 1)

    def test_password_is_not_bypassed_by_unverified_option(self):
        with mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(server.focused_text, "read", return_value={"ok": False, "error": "password_control", "focus_id": "1"}), \
             mock.patch.object(server, "paste_text") as paste:
            result = json.loads(server.type_text("hello", allow_unverified=True))
        self.assertEqual(result["error"], "password_control")
        paste.assert_not_called()

    def test_batch_confirmation_and_one_time_consumption(self):
        actions = [{"tool": "press_keys", "arguments": {"keys": "ctrl+a"}}] * 3
        gate = server.ConfirmationGate("always", [])
        with mock.patch.object(server, "GATE", gate), \
             mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(winapi, "focused_hwnd", return_value=10), \
             mock.patch.object(winapi, "press_keys", return_value={"keys": "ctrl+a"}) as keys:
            pending = json.loads(server.input_batch(1, actions))
            keys.assert_not_called()
            result = json.loads(server.input_batch(1, actions, pending["confirm_token"]))
            self.assertTrue(result["ok"], result)
            self.assertEqual(keys.call_count, 3)
            replay = json.loads(server.input_batch(1, actions, pending["confirm_token"]))
            self.assertEqual(replay["error"], "invalid_confirm_token")
            self.assertEqual(keys.call_count, 3)
        self.assertIsNone(server._BATCH_ACTION.get())

    def test_batch_stops_on_first_failure(self):
        actions = [{"tool": "press_keys", "arguments": {"keys": "ctrl+a"}}] * 3
        with mock.patch.object(server, "GATE", server.ConfirmationGate("off", [])), \
             mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(winapi, "focused_hwnd", return_value=10), \
             mock.patch.object(winapi, "press_keys", side_effect=ValueError("changed")) as keys:
            result = json.loads(server.input_batch(1, actions))
        self.assertEqual(result["error"], "batch_stopped")
        self.assertEqual(keys.call_count, 1)
        self.assertIsNone(server._BATCH_ACTION.get())

    def test_input_content_verification(self):
        from focused_text import insertion_matches
        self.assertTrue(insertion_matches("abc", "a中文bc", "中文"))
        self.assertTrue(insertion_matches("abc", "中文", "中文"))
        self.assertFalse(insertion_matches("abc", "axy", "中文"))
        self.assertFalse(insertion_matches("中文", "中文", "中文"))

    def test_explicit_input_target_rejects_drift(self):
        with mock.patch.object(winapi, "foreground_info", return_value=_window(2)), \
             mock.patch.object(server, "paste_text") as paste:
            result = json.loads(server.type_text("hello", hwnd=1))
        self.assertEqual(result["error"], "target_changed")
        paste.assert_not_called()

    def test_paste_dispatch_is_not_verified_success(self):
        before = {"ok": True, "editable": True, "focus_id": "1", "text": ""}
        with mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(server, "_gate", return_value=None), \
             mock.patch.object(server.focused_text, "read", return_value=before), \
             mock.patch.object(server, "paste_text", return_value={"paste_ok": True}):
            result = json.loads(server.type_text("hello", hwnd=1))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "paste_unverified")
        self.assertTrue(result["dispatched"])

    def test_paste_verified_content(self):
        before = {"ok": True, "editable": True, "focus_id": "1", "text": ""}
        after = {**before, "text": "hello"}
        with mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(server, "_gate", return_value=None), \
             mock.patch.object(server.focused_text, "read", side_effect=[before, before, after]), \
             mock.patch.object(server, "paste_text", return_value={"paste_ok": True}):
            result = json.loads(server.type_text("hello", hwnd=1))
        self.assertTrue(result["ok"])
        self.assertTrue(result["verified"])

    def test_unicode_newline_does_not_dispatch_bare_enter(self):
        with mock.patch.object(winapi, "_ensure_foreground"), \
             mock.patch.object(winapi, "_key_event") as event, \
             mock.patch.object(winapi, "press_keys") as keys:
            winapi.type_text("\n", expected_hwnd=1)
        keys.assert_called_once_with("shift+enter", expected_hwnd=1)
        event.assert_not_called()

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
             mock.patch.object(winapi.user32, "SetCursorPos", return_value=True), \
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


class FocusWorkerTests(unittest.TestCase):
    def test_reuses_worker_and_closes_it_on_eof(self):
        module = server.focused_text
        real_popen = subprocess.Popen
        processes = []
        program = "import sys,json\nfor line in sys.stdin:\n r=json.loads(line);print(json.dumps({'ok':True,'text':str(r['hwnd'])}),flush=True)"
        def spawn(_args, **kwargs):
            process = real_popen([sys.executable, '-u', '-c', program], **kwargs)
            processes.append(process)
            return process
        reader = module.FocusReader(timeout=10)
        with mock.patch.object(module.subprocess, 'Popen', side_effect=spawn):
            try:
                self.assertEqual(reader.read(1, 10)['text'], '1')
                self.assertEqual(reader.read(2, 10)['text'], '2')
                self.assertEqual(len(processes), 1)
            finally:
                reader.close()
        self.assertIsNotNone(processes[0].poll())

    def test_worker_timeout_releases_process_and_next_call_starts_fresh(self):
        module = server.focused_text
        real_popen = subprocess.Popen
        processes = []
        programs = ["import sys,time\nfor line in sys.stdin: time.sleep(.3)",
                    "import sys,json\nfor line in sys.stdin: print(json.dumps({'ok':False,'error':'target_changed'}),flush=True)"]
        def spawn(_args, **kwargs):
            process = real_popen([sys.executable, '-u', '-c', programs[len(processes)]], **kwargs)
            processes.append(process)
            return process
        reader = module.FocusReader(timeout=.1)
        with mock.patch.object(module.subprocess, 'Popen', side_effect=spawn):
            try:
                with self.assertRaises(TimeoutError): reader.read(1, 10)
                self.assertIsNone(reader.process)
                self.assertIsNotNone(processes[0].poll())
                reader.timeout = 10
                self.assertEqual(reader.read(2, 10)['error'], 'target_changed')
            finally:
                reader.close()
        self.assertTrue(all(process.poll() is not None for process in processes))

    def test_transport_timeout_is_not_retried_as_delayed_text(self):
        with mock.patch.object(server.focused_text, 'read', side_effect=TimeoutError('fixture timeout')) as read:
            ok, reason = server.focused_text.verify_insertion(1, {'ok':True,'text':'before','focus_id':'1'}, 'text')
        self.assertFalse(ok)
        self.assertEqual(reason, 'fixture timeout')
        self.assertEqual(read.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
