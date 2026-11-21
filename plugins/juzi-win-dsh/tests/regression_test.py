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

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC_DIR))

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
             mock.patch.object(winapi, "current_cursor", return_value={"x": 100, "y": 100}), \
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
        source = (SRC_DIR / "paste_text.py").read_text(encoding="utf-8")
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


class OcrWorkerTests(unittest.TestCase):
    def test_reuses_worker_and_closes_on_eof(self):
        module = server.ocr
        real_popen = subprocess.Popen
        processes = []
        program = (
            "import sys,json\n"
            "for line in sys.stdin:\n"
            " r=json.loads(line);"
            "print(json.dumps({'ok':True,'engine':'windows-ocr','lang':r['lang_tag'],'lines':[]}),flush=True)"
        )
        def spawn(_args, **kwargs):
            proc = real_popen([sys.executable, "-u", "-c", program], **kwargs)
            processes.append(proc)
            return proc
        worker = module.OcrWorker(timeout=10)
        with mock.patch.object(module.subprocess, "Popen", side_effect=spawn):
            try:
                r1 = worker.recognize_path(Path("a.png"), "zh-Hans-CN")
                r2 = worker.recognize_path(Path("b.png"), "en-US")
                self.assertTrue(r1["ok"] and r2["ok"])
                self.assertEqual(r2["lang"], "en-US")
                self.assertEqual(len(processes), 1)
            finally:
                worker.close()
        self.assertIsNotNone(processes[0].poll())

    def test_worker_timeout_recovers_on_next_call(self):
        module = server.ocr
        real_popen = subprocess.Popen
        processes = []
        programs = [
            "import sys,time\nfor line in sys.stdin: time.sleep(.4)",
            "import sys,json\nfor line in sys.stdin: print(json.dumps({'ok':True,'engine':'windows-ocr','lang':'zh-Hans-CN','lines':[]}),flush=True)",
        ]
        def spawn(_args, **kwargs):
            proc = real_popen([sys.executable, "-u", "-c", programs[len(processes)]], **kwargs)
            processes.append(proc)
            return proc
        worker = module.OcrWorker(timeout=0.1)
        with mock.patch.object(module.subprocess, "Popen", side_effect=spawn):
            try:
                with self.assertRaises(TimeoutError):
                    worker.recognize_path(Path("a.png"), "zh-Hans-CN")
                self.assertIsNone(worker.process)
                self.assertIsNotNone(processes[0].poll())
                worker.timeout = 10
                r2 = worker.recognize_path(Path("b.png"), "zh-Hans-CN")
                self.assertTrue(r2["ok"])
            finally:
                worker.close()
        self.assertTrue(all(p.poll() is not None for p in processes))


class PerformanceUpgradeTests(unittest.TestCase):
    def test_screenshot_jpeg_format_and_validation(self):
        with mock.patch.object(winapi, "screen_metrics", return_value={"x": 0, "y": 0, "width": 100, "height": 100}), \
             mock.patch.object(security, "forbidden_windows", return_value=[]), \
             mock.patch.object(winapi, "capture", return_value=(b"\xff\xd8\xff", {"width": 100, "height": 100, "mime_type": "image/jpeg", "format": "jpeg"})) as cap:
            res = server.screenshot(max_width=960, format="jpeg", quality=80)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[1]["mimeType"], "image/jpeg")
        cap.assert_called_once_with(max_width=960, hwnd=None, image_format="jpeg", quality=80)
        bad = server._call_tool("screenshot", {"format": "webp"})
        self.assertTrue(bad["isError"])

    def test_click_after_screenshot_attaches_image_block(self):
        fake_shot = [
            {"type": "text", "text": json.dumps({"ok": True, "width": 800, "height": 600, "format": "jpeg"})},
            {"type": "image", "data": "AAAA", "mimeType": "image/jpeg"},
        ]
        with mock.patch.object(server, "GATE", server.ConfirmationGate("off", [])), \
             mock.patch.object(winapi, "resolve_click_point", return_value=(10, 20)), \
             mock.patch.object(winapi, "window_at_point", return_value=_window()), \
             mock.patch.object(winapi, "click", return_value={"x": 10, "y": 20, "target": _window()}), \
             mock.patch.object(server, "screenshot", return_value=fake_shot) as shot:
            res = server.click(10, 20, after_screenshot=True, after_wait_ms=0, screenshot_max_width=960, screenshot_format="jpeg")
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[1]["mimeType"], "image/jpeg")
        payload = json.loads(res[0]["text"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["after_screenshot"]["width"], 800)
        shot.assert_called_once_with(hwnd=None, max_width=960, format="jpeg")

    def test_action_batch_confirmation_image_and_forbidden_guard(self):
        actions = [
            {"tool": "click", "arguments": {"x": 10, "y": 20}},
            {"tool": "wait", "arguments": {"condition": "timeout", "timeout_ms": 0}},
            {"tool": "screenshot", "arguments": {"max_width": 960, "format": "jpeg"}},
        ]
        fake_shot = [
            {"type": "text", "text": json.dumps({"ok": True, "width": 960, "height": 640, "format": "jpeg"})},
            {"type": "image", "data": "BBBB", "mimeType": "image/jpeg"},
        ]
        gate = server.ConfirmationGate("always", [])
        with mock.patch.object(server, "GATE", gate), \
             mock.patch.object(winapi, "foreground_info", return_value=_window()), \
             mock.patch.object(winapi, "resolve_click_point", return_value=(10, 20)), \
             mock.patch.object(winapi, "window_at_point", return_value=_window()), \
             mock.patch.object(winapi, "click", return_value={"x": 10, "y": 20, "target": _window()}) as clk, \
             mock.patch.dict(server.TOOL_FUNCTIONS, {"screenshot": mock.MagicMock(return_value=fake_shot)}):
            pending = json.loads(server.action_batch(actions))
            self.assertEqual(pending["status"], "confirmation_required")
            clk.assert_not_called()
            done = server.action_batch(actions, confirm_token=pending["confirm_token"])
        self.assertIsInstance(done, list)
        self.assertEqual(len(done), 2)
        self.assertEqual(done[1]["mimeType"], "image/jpeg")
        summary = json.loads(done[0]["text"])
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["completed_steps"], 3)
        self.assertFalse(server._ACTION_BATCH_CONFIRMED.get())

        # Forbidden window must NEVER be bypassed inside action_batch even with confirm_mode=off
        blocked_win = _window(hwnd=99, process="consent.exe", title="用户帐户控制")
        with mock.patch.object(server, "GATE", server.ConfirmationGate("off", [])), \
             mock.patch.object(winapi, "resolve_click_point", return_value=(10, 20)), \
             mock.patch.object(winapi, "window_at_point", return_value=blocked_win), \
             mock.patch.object(winapi, "click") as clk2:
            res = json.loads(server.action_batch([{"tool": "click", "arguments": {"x": 10, "y": 20}}]))
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "forbidden_window")
        clk2.assert_not_called()


class ScreenlessPerceptionTests(unittest.TestCase):
    def test_ui_tree_worker_reuses_single_process(self):
        import ui_tree as module
        real_popen = subprocess.Popen
        processes = []
        program = (
            "import sys,json\n"
            "for i,line in enumerate(sys.stdin,1):\n"
            " req=json.loads(line)\n"
            " print(json.dumps({'ok':True,'hwnd':req['hwnd'],'count':i,'compact':'Button \"OK\" (10,20)','elements':[]}),flush=True)\n"
        )
        def spawn(_args, **kwargs):
            proc = real_popen([sys.executable, "-u", "-c", program], **kwargs)
            processes.append(proc)
            return proc
        worker = module.UiTreeWorker(timeout=5)
        with mock.patch.object(module.subprocess, "Popen", side_effect=spawn):
            try:
                r1 = worker.inspect(hwnd=100)
                r2 = worker.inspect(hwnd=100)
                self.assertEqual((r1["count"], r2["count"]), (1, 2))
                self.assertEqual(len(processes), 1)
                self.assertIsNone(processes[0].poll())
            finally:
                worker.close()
        self.assertIsNotNone(processes[0].poll())

    def test_inspect_ui_forbidden_guard_and_action_batch(self):
        import ui_tree as module
        blocked = _window(hwnd=99, process="consent.exe", title="用户帐户控制")
        with mock.patch.object(winapi, "window_info", return_value=blocked), \
             mock.patch.object(module, "inspect") as mock_inspect:
            res = json.loads(server.inspect_ui(hwnd=99))
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "forbidden_window")
        mock_inspect.assert_not_called()

        fake_ui = {
            "ok": True, "hwnd": 100, "count": 2, "visited_nodes": 12,
            "truncated": False, "elapsed_ms": 45,
            "coordinate_space": "screen-physical-pixels",
            "compact": 'RadioButton "CPU" (100,200) [selected]\nRadioButton "H100 GPU" (200,200) [DISABLED]',
            "elements": [
                {"type": "RadioButton", "name": "CPU", "cx": 100, "cy": 200, "enabled": True, "selected": True},
                {"type": "RadioButton", "name": "H100 GPU", "cx": 200, "cy": 200, "enabled": False},
            ],
        }
        with mock.patch.object(winapi, "window_info", return_value=_window(hwnd=100)), \
             mock.patch.object(module, "inspect", return_value=dict(fake_ui)) as inspect:
            batch_res = json.loads(server.action_batch([
                {"tool": "wait", "arguments": {"condition": "timeout", "timeout_ms": 0}},
                {"tool": "inspect_ui", "arguments": {"hwnd": 100, "query": "GPU", "include_visible_text": True}},
            ]))
        self.assertTrue(inspect.call_args.kwargs["include_visible_text"])
        self.assertFalse(inspect.call_args.kwargs["include_hierarchy"])
        self.assertTrue(batch_res["ok"])
        self.assertEqual(batch_res["completed_steps"], 2)
        self.assertIn("H100 GPU", batch_res["results"][1]["compact"])
        self.assertIn("[DISABLED]", batch_res["results"][1]["compact"])

    def test_read_screen_text_extracts_cjk_and_latin_blocks(self):
        import ocr as ocr_mod
        from PIL import Image
        lines = [
            {"text": "可 用 200 个", "words": [
                {"text": "可", "x": 10, "y": 20, "w": 16, "h": 20},
                {"text": "用", "x": 28, "y": 20, "w": 16, "h": 20},
                {"text": "200", "x": 46, "y": 20, "w": 30, "h": 20},
                {"text": "个", "x": 78, "y": 20, "w": 16, "h": 20},
            ]},
            {"text": "Colab Pro", "words": [
                {"text": "Colab", "x": 10, "y": 60, "w": 50, "h": 20},
                {"text": "Pro", "x": 66, "y": 60, "w": 30, "h": 20},
            ]},
        ]
        blocks = ocr_mod.extract_text_blocks(lines, max_items=10)
        self.assertEqual([b["text"] for b in blocks], ["可用200个", "Colab Pro"])

        img = Image.new("RGB", (200, 100), color="white")
        meta = {"mode": "window", "hwnd": 100, "width": 200, "height": 100, "origin": {"x": 50, "y": 40}, "scale": 1.0}
        with mock.patch.object(winapi, "window_info", return_value=_window(hwnd=100)), \
             mock.patch.object(winapi, "client_metrics", return_value={"x": 50, "y": 40, "width": 200, "height": 100}), \
             mock.patch.object(security, "forbidden_windows", return_value=[]), \
             mock.patch.object(winapi, "grab_image", return_value=(img, meta)), \
             mock.patch.object(ocr_mod, "recognize", return_value={"ok": True, "engine": "windows-ocr", "lang": "zh-Hans-CN", "lines": lines}):
            res = json.loads(server.read_screen_text(hwnd=100, include_items=True))
        self.assertTrue(res["ok"])
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["items"][0]["text"], "可用200个")
        self.assertEqual(res["items"][0]["cx"], 50 + 52)
        self.assertIn('"Colab Pro"', res["compact"])


class WindowCaptureTests(unittest.TestCase):
    def test_wgc_region_coordinates_in_batch(self):
        window = _window(hwnd=100)
        client = {"x": -460, "y": 30, "width": 300, "height": 200}
        window["rect"] = {"x": -470, "y": 0, "width": 320, "height": 250}
        region = {"x": -400, "y": 60, "width": 120, "height": 80}
        lines = [{"words": [{"text": "Target", "x": 10, "y": 20, "w": 40, "h": 16}]}]
        args = {"capture_mode": "wgc", "hwnd": 100, "region": region, "include_items": True}
        with mock.patch.object(winapi, "window_info", return_value=window), \
             mock.patch.object(winapi, "client_metrics", return_value=client), \
             mock.patch.object(security, "forbidden_windows", return_value=[]), \
             mock.patch.object(server.ocr, "capture_window_png", return_value=b"window") as capture, \
             mock.patch.object(server.ocr, "recognize", return_value={"ok": True, "lines": lines}) as recognize:
            batch = json.loads(server.action_batch([{"tool": "read_screen_text", "arguments": args}]))
        self.assertTrue(batch["ok"])
        result = batch["results"][0]
        capture.assert_called_once_with(100, window["rect"], region)
        recognize.assert_called_once_with(b"window", "chi_sim+eng")
        self.assertEqual(result["image"]["capture_method"], "wgc")
        self.assertEqual((result["items"][0]["cx"], result["items"][0]["cy"]), (-370, 88))

    def test_wgc_rejects_invalid_targets_and_never_substitutes_desktop_pixels(self):
        window = _window(hwnd=100)
        with mock.patch.object(winapi, "window_info", return_value=window) as info, \
             mock.patch.object(winapi, "client_metrics", return_value=window["rect"]), \
             mock.patch.object(security, "forbidden_windows", return_value=[]) as intersecting, \
             mock.patch.object(winapi, "grab_image") as desktop, \
             mock.patch.object(server.ocr, "capture_window_png") as capture, \
             mock.patch.object(server.ocr, "recognize") as recognize:
            def error(**args):
                return json.loads(server.read_screen_text(capture_mode="wgc", **args))["error_code"]

            self.assertEqual(error(), "invalid_hwnd")
            info.return_value = {**window, "minimized": True}
            self.assertEqual(error(hwnd=100), "window_minimized")
            info.return_value = _window(hwnd=100, process="consent.exe")
            self.assertEqual(error(hwnd=100), "forbidden_window")
            info.return_value = window
            self.assertEqual(error(hwnd=100, region={**window["rect"], "x": -1}), "invalid_region")
            intersecting.return_value = [_window(hwnd=200, process="consent.exe")]
            self.assertEqual(error(hwnd=100), "forbidden_window")
            capture.assert_not_called()
            intersecting.return_value = []
            capture.side_effect = RuntimeError("No frame")
            self.assertEqual(error(hwnd=100), "wgc_capture_failed")
            capture.side_effect = None
            info.side_effect = [window, {**window, "rect": {**window["rect"], "x": 10}}]
            self.assertEqual(error(hwnd=100), "target_changed")
            desktop.assert_not_called()
            recognize.assert_not_called()


class ChromeCdpTests(unittest.TestCase):
    def test_websocket_rfc6455_and_cdp_manager_end_to_end(self):
        import base64
        import hashlib
        import socket
        import struct
        import threading
        import cdp as cdp_mod

        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]

        def ws_server():
            conn, _ = srv.accept()
            try:
                buf = b""
                while b"\r\n\r\n" not in buf:
                    buf += conn.recv(4096)
                headers = {}
                for line in buf.decode("latin-1").split("\r\n")[1:]:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        headers[k.strip().lower()] = v.strip()
                accept = base64.b64encode(
                    hashlib.sha1((headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
                ).decode()
                conn.sendall(
                    f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n".encode()
                )
                # Send a PING frame first to verify client PONG handling
                conn.sendall(bytes([0x89, 2]) + b"hi")

                def send_ws_json(obj):
                    data = json.dumps(obj).encode("utf-8")
                    if len(data) < 126:
                        hdr = bytes([0x81, len(data)])
                    else:
                        hdr = bytes([0x81, 126]) + struct.pack("!H", len(data))
                    conn.sendall(hdr + data)

                while True:
                    head = conn.recv(2)
                    if not head or (head[0] & 0x0F) == 0x8:
                        break
                    opcode = head[0] & 0x0F
                    masked = bool(head[1] & 0x80)
                    ln = head[1] & 0x7F
                    if ln == 126:
                        ln = struct.unpack("!H", conn.recv(2))[0]
                    mask = conn.recv(4) if masked else b""
                    raw = b""
                    while len(raw) < ln:
                        raw += conn.recv(ln - len(raw))
                    if masked:
                        raw = bytes(b ^ mask[i & 3] for i, b in enumerate(raw))
                    if opcode == 0xA:  # PONG
                        continue
                    req = json.loads(raw.decode("utf-8"))
                    rid, method = req["id"], req["method"]
                    if method == "Target.getTargets":
                        send_ws_json({"id": rid, "result": {"targetInfos": [
                            {"targetId": "t1", "type": "page", "title": "Untitled - Colab", "url": "https://colab.research.google.com/", "attached": False},
                        ]}})
                    elif method == "Target.attachToTarget":
                        send_ws_json({"id": rid, "result": {"sessionId": "s1"}})
                    elif method == "Runtime.evaluate":
                        expr = req["params"]["expression"]
                        if "1" == expr:
                            send_ws_json({"id": rid, "sessionId": "s1", "result": {"result": {"value": 1}}})
                        elif "__juziCdpRefs" in expr and "walk" in expr:
                            send_ws_json({"id": rid, "sessionId": "s1", "result": {"result": {"value": {
                                "title": "Colab", "url": "https://colab.research.google.com/",
                                "ready_state": "complete", "count": 2,
                                "compact": '[1] radio "CPU" [selected]\n[2] radio "H100 GPU" [DISABLED]',
                                "elements": [{"ref": 1}, {"ref": 2}],
                            }}}})
                        else:
                            send_ws_json({"id": rid, "sessionId": "s1", "result": {"result": {"value": {
                                "ok": True, "dispatched_via": "cdp_mouse", "tag": "button", "label": "连接", "cx": 100, "cy": 50,
                            }}}})
                    elif method == "Input.dispatchMouseEvent":
                        send_ws_json({"id": rid, "sessionId": "s1", "result": {}})
            finally:
                conn.close()
                srv.close()

        t = threading.Thread(target=ws_server, daemon=True)
        t.start()
        mgr = cdp_mod.CdpManager()
        ws_url = f"ws://127.0.0.1:{port}/devtools/browser/mock"
        try:
            tabs = mgr.execute("list_tabs", ws_url=ws_url)
            self.assertEqual(tabs["count"], 1)
            page = mgr.execute("inspect_page", ws_url=ws_url, target_id="t1")
            self.assertIn("[DISABLED]", page["compact"])
            self.assertNotIn("elements", page)
            clicked = mgr.execute("click", ws_url=ws_url, target_id="t1", ref=1, wait_ms=0, after_inspect=True)
            self.assertTrue(clicked["ok"])
            self.assertIn("page", clicked)
        finally:
            mgr.close()
            t.join(timeout=2)

    def test_chrome_cdp_forbidden_pages_and_confirmation_gate(self):
        import cdp as cdp_mod
        # Password settings URL must be rejected immediately
        blocked = json.loads(server.chrome_cdp(action="open_url", url="chrome://settings/passwords"))
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error_code"], "forbidden_page")

        self.assertIsNotNone(cdp_mod.forbidden_page_reason("https://my.1password.com", "1Password - 登录"))

        # Read action bypasses confirmation gate; write action requires confirmation when mode=always
        gate = server.ConfirmationGate("always", [])
        with mock.patch.object(server, "GATE", gate), \
             mock.patch.object(cdp_mod, "execute", return_value={"ok": True, "count": 0, "tabs": []}) as mock_exec:
            ro = json.loads(server.chrome_cdp(action="list_tabs"))
            self.assertTrue(ro["ok"])
            mock_exec.assert_called_once()

        with mock.patch.object(server, "GATE", gate), \
             mock.patch.object(cdp_mod, "execute", return_value={"ok": True, "action": "click"}) as mock_exec2:
            pending = json.loads(server.chrome_cdp(action="click", ref=1))
            self.assertEqual(pending["status"], "confirmation_required")
            mock_exec2.assert_not_called()
            done = json.loads(server.chrome_cdp(action="click", ref=1, confirm_token=pending["confirm_token"]))
            self.assertTrue(done["ok"])
            mock_exec2.assert_called_once()


class CursorOverlayTests(unittest.TestCase):
    def test_render_frames_and_env_toggle(self):
        import os
        import cursor_overlay as co
        # Guard against Win32 constant typos (0x0011 is WM_QUERYENDSESSION, not WM_TIMER!)
        self.assertEqual(co.WM_TIMER, 0x0113)
        self.assertEqual(co.WM_CLOSE, 0x0010)
        self.assertEqual(co.WM_DESTROY, 0x0002)
        normal, ripples, pressed = co._render_frames()
        expected_bytes = co.CANVAS_SIZE * co.CANVAS_SIZE * 4
        self.assertEqual(len(normal), expected_bytes)
        self.assertEqual(len(pressed), expected_bytes)
        self.assertEqual(len(ripples), co.RIPPLE_FRAMES)
        self.assertTrue(any(normal))
        with mock.patch.dict(os.environ, {"JUZI_WIN_DSH_CURSOR": "off"}):
            ov = co.CursorOverlay()
            ov.notify_click(100, 100)
            self.assertFalse(ov._started)
            with ov.work_scope(50, 60):
                self.assertEqual(ov._active_depth, 0)
        ov2 = co.CursorOverlay()
        with mock.patch.object(ov2, "_ensure_started", return_value=True), \
             mock.patch.object(ov2, "_wake"):
            with ov2.work_scope(10, 20):
                self.assertEqual(ov2._active_depth, 1)
            self.assertEqual(ov2._active_depth, 0)


class TakeoverAndSmartWaitTests(unittest.TestCase):
    def test_action_batch_stops_when_user_moves_physical_mouse(self):
        actions = [
            {"tool": "click", "arguments": {"x": 100, "y": 100}},
            {"tool": "click", "arguments": {"x": 300, "y": 300}},
        ]
        # Step 1 leaves AI cursor at (100,100); before Step 2 user moves real mouse to (260,260)
        with mock.patch.object(server, "GATE", server.ConfirmationGate("off", [])), \
             mock.patch.object(winapi, "resolve_click_point", side_effect=[(100, 100), (300, 300)]), \
             mock.patch.object(winapi, "window_at_point", return_value=_window()), \
             mock.patch.object(winapi, "click", return_value={"x": 100, "y": 100, "cursor": {"x": 100, "y": 100}, "target": _window()}) as clk, \
             mock.patch.object(winapi, "current_cursor", return_value={"x": 260, "y": 260}):
            res = json.loads(server.action_batch(actions))
        self.assertFalse(res["ok"])
        self.assertEqual(res["error_code"], "user_interrupted")
        self.assertEqual(res["failed_step"], 1)
        self.assertEqual(clk.call_count, 1)

    def test_drag_releases_button_and_aborts_on_user_mouse_takeover(self):
        events = []
        # Anchor after SetCursorPos(0,0) is (0,0), then after sleep user moved cursor to (200,200)
        cursors = [{"x": 0, "y": 0}, {"x": 200, "y": 200}, {"x": 200, "y": 200}]
        with mock.patch.object(winapi, "resolve_click_point", side_effect=[(0, 0), (100, 100)]), \
             mock.patch.object(winapi.user32, "SetCursorPos", return_value=True), \
             mock.patch.object(winapi, "current_cursor", side_effect=cursors), \
             mock.patch.object(winapi, "window_at_point", return_value=_window()), \
             mock.patch.object(winapi, "_mouse_event", side_effect=lambda *a: events.append(a[0])), \
             mock.patch.object(time, "sleep"):
            raw = winapi.drag(0, 0, 100, 100, hold_ms_before=10)
        self.assertTrue(raw["user_interrupted"])
        self.assertEqual(events, [])  # Interrupted during hold_ms_before before even pressing mouse down!

        # Interrupted mid-drag after pressing mouse down must release button cleanly
        events2 = []
        cursors2 = [
            {"x": 0, "y": 0}, {"x": 0, "y": 0},        # hold_ms_before stable
            {"x": 50, "y": 50}, {"x": 220, "y": 220},  # step 1 user yanked mouse away!
            {"x": 220, "y": 220},
        ]
        with mock.patch.object(winapi, "resolve_click_point", side_effect=[(0, 0), (100, 100), (0, 0), (100, 100)]), \
             mock.patch.object(winapi.user32, "SetCursorPos", return_value=True), \
             mock.patch.object(winapi, "current_cursor", side_effect=cursors2), \
             mock.patch.object(winapi, "window_at_point", return_value=_window()), \
             mock.patch.object(winapi, "_mouse_event", side_effect=lambda *a: events2.append(a[0])), \
             mock.patch.object(time, "sleep"):
            with mock.patch.object(server, "GATE", server.ConfirmationGate("off", [])):
                resp = json.loads(server.drag(0, 0, 100, 100, steps=2))
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error_code"], "user_interrupted")
        self.assertEqual(events2, [0x0002, 0x0004])  # Down then guaranteed Up!

    def test_wait_ui_text_ui_gone_and_ocr_text(self):
        win = _window(hwnd=100)
        empty_ui = {"ok": True, "count": 0, "compact": ""}
        hit_ui = {"ok": True, "count": 1, "compact": 'Button "连接" (1850,125)'}
        with mock.patch.object(winapi, "window_info", return_value=win), \
             mock.patch.object(server.ui_tree, "inspect", side_effect=[empty_ui, hit_ui]):
            r1 = json.loads(server.wait(condition="ui_text", hwnd=100, text="连接", timeout_ms=2000, poll_ms=50))
        self.assertTrue(r1["ok"])
        self.assertEqual(r1["count"], 1)
        self.assertIn("1850,125", r1["compact"])

        with mock.patch.object(winapi, "window_info", return_value=win), \
             mock.patch.object(server.ui_tree, "inspect", side_effect=[hit_ui, empty_ui]):
            r2 = json.loads(server.wait(condition="ui_gone", hwnd=100, text="加载中", timeout_ms=2000, poll_ms=50))
        self.assertTrue(r2["ok"])

        ocr_miss = json.dumps({"ok": True, "count": 0, "results": []})
        ocr_hit = json.dumps({"ok": True, "count": 1, "results": [{"text": "就绪", "cx": 88, "cy": 99}]})
        with mock.patch.object(server, "find_text", side_effect=[ocr_miss, ocr_hit]):
            r3 = json.loads(server.wait(condition="ocr_text", hwnd=100, text="就绪", timeout_ms=2000, poll_ms=50))
        self.assertTrue(r3["ok"])
        self.assertEqual(r3["results"][0]["cx"], 88)


if __name__ == "__main__":
    unittest.main(verbosity=2)
