"""Offline credential-boundary regressions; only dummy credentials reach loopback fixtures."""
import io
import json
import os
import sys
import threading
import types
import unittest
import urllib.error
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import server

KEY = "fixture-secret-not-a-real-credential"


class Handler(BaseHTTPRequestHandler):
    visits = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.visits.append((self.path, self.headers.get("Authorization")))
        if self.path.startswith("/redirect/"):
            self.send_response(int(self.path.rsplit("/", 1)[1]))
            self.send_header("Location", self.server.target + "/stolen")
            self.end_headers()
            return
        if self.path == "/error":
            self.send_response(401)
            body = {"message": KEY}
        elif self.path == "/retry" and sum(p == "/retry" for p, _ in self.visits) == 1:
            self.send_response(503)
            body = {"message": KEY}
        else:
            self.send_response(200)
            body = {"content": KEY} if self.path == "/echo" else {
                "results": [{"title": "fixture", "url": "https://example.com"}],
                "content": "fixture content",
            }
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.target = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.origin = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.origin.target = f"http://127.0.0.1:{cls.target.server_port}"
        for instance in (cls.origin, cls.target):
            threading.Thread(target=instance.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for instance in (cls.origin, cls.target):
            instance.shutdown()
            instance.server_close()

    def setUp(self):
        Handler.visits.clear()
        server._api_key_cached.cache_clear()

    def request(self, path):
        # HTTPS policy is tested separately. No real key or external endpoint is used here.
        with patch.object(server, "_api_key", return_value=KEY), patch.object(
            server, "_endpoint", return_value=f"http://127.0.0.1:{self.origin.server_port}{path}"
        ), patch.dict(os.environ, {"NO_PROXY": "127.0.0.1"}), patch.object(server.time, "sleep"):
            return server._post(path, {})

    def test_all_redirects_are_blocked(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                result = self.request(f"/redirect/{status}")
                self.assertEqual(result["error"], "redirect_blocked")
                self.assertEqual(result["status"], status)
        self.assertFalse(any(path == "/stolen" for path, _ in Handler.visits))
        previous = self.origin.target
        try:
            self.origin.target = f"http://127.0.0.1:{self.origin.server_port}"
            self.assertEqual(self.request("/redirect/302")["error"], "redirect_blocked")
            self.assertFalse(any(path == "/stolen" for path, _ in Handler.visits))
        finally:
            self.origin.target = previous

    def test_system_registry_uses_actual_environment_location(self):
        opened = []

        def open_key(root, path):
            opened.append((root, path))
            if root == "user":
                raise FileNotFoundError()
            from contextlib import nullcontext
            return nullcontext("fixture-handle")

        fake = types.SimpleNamespace(HKEY_CURRENT_USER="user", HKEY_LOCAL_MACHINE="system", OpenKey=open_key,
                                     QueryValueEx=lambda handle, name: (KEY, 1))
        with patch.dict(sys.modules, {"winreg": fake}):
            self.assertEqual(server._windows_env("DEEPSEEK_API_KEY"), KEY)
        self.assertEqual(opened, [("user", "Environment"), ("system", r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")])

    def test_missing_or_malformed_key_never_reaches_network(self):
        for key in ("", "dummy\nvalue", "中文", "dummy\x7fvalue"):
            with patch.object(server, "_api_key", return_value=key), patch.object(server._HTTP, "open") as network:
                result = server._post("/test", {})
                self.assertEqual(result["error"], "missing_api_key" if not key else "invalid_api_key")
                network.assert_not_called()

    def test_errors_do_not_echo_credentials(self):
        result = self.request("/error")
        self.assertEqual(result["status"], 401)
        self.assertNotIn(KEY, json.dumps(result))
        with patch.object(server, "_api_key", return_value=KEY), patch.object(
            server._HTTP, "open", side_effect=urllib.error.URLError(KEY)
        ):
            self.assertNotIn(KEY, json.dumps(server._post("/network", {})))

    def test_success_echo_is_blocked(self):
        self.assertEqual(self.request("/echo")["error"], "unsafe_response")

    def test_success_and_retry_keep_behavior(self):
        for path in ("/success", "/retry"):
            with self.subTest(path=path):
                result = self.request(path)
                self.assertEqual(result["content"], "fixture content")
                self.assertEqual(len(result["results"]), 1)
        self.assertTrue(all(auth == "Bearer " + KEY for _, auth in Handler.visits))

    def test_only_dedicated_key_is_read(self):
        with patch.dict(os.environ, {"ANTHROPIC_AUTH_TOKEN": KEY}, clear=True), patch.object(
            server, "_windows_env", return_value=""
        ) as registry:
            self.assertEqual(server._api_key(), "")
            registry.assert_called_once_with("DEEPSEEK_API_KEY")
        server._api_key_cached.cache_clear()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": KEY}, clear=True), patch.object(
            server, "_windows_env"
        ) as registry:
            self.assertEqual(server._api_key(), KEY)
            registry.assert_not_called()

    def test_invalid_gateway_fails_before_reading_key(self):
        for value in ("http://example.com", "https://user:pass@example.com", "https://example.com/?secret=x", "https://example.com/#x", "https://example.com:bad"):
            with self.subTest(value=value), patch.object(server, "BASE_URL", value), patch.object(server, "_api_key") as key:
                self.assertEqual(server._post("/test", {})["error"], "invalid_api_base")
                key.assert_not_called()
        with patch.object(server, "BASE_URL", "https://api.deepseek.com"):
            self.assertEqual(server._endpoint("/v1/tools/search"), "https://api.deepseek.com/v1/tools/search")

    def test_tool_success_failure_and_usage(self):
        with patch.object(server, "_post", return_value={"results": [{"title": "fixture"}], "content": "abcdef"}), patch.object(server, "_record_usage") as usage:
            self.assertEqual(json.loads(server.search("test"))["count"], 1)
            self.assertEqual(json.loads(server.fetch("https://example.com", max_chars=3))["content"], "abc")
            self.assertEqual(usage.call_count, 2)
            self.assertEqual(json.loads(server.search(" "))["error"], "invalid_query")
            self.assertEqual(json.loads(server.fetch("bad"))["error"], "invalid_url")
            self.assertEqual(usage.call_count, 2)
        with patch.object(server, "_post", return_value={"error": "http_error", "status": 401}), patch.object(server, "_record_usage") as usage:
            self.assertEqual(json.loads(server.search("test"))["status"], 401)
            self.assertEqual(json.loads(server.fetch("https://example.com"))["status"], 401)
            usage.assert_not_called()

    def test_invalid_numeric_config_does_not_print_values(self):
        stderr = io.StringIO()
        with patch.dict(os.environ, {"AUDIT_NUMERIC": KEY}), redirect_stderr(stderr):
            self.assertEqual(server._env_float("AUDIT_NUMERIC", 60), 60)
            self.assertEqual(server._env_int("AUDIT_NUMERIC", 1), 1)
        self.assertNotIn(KEY, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
