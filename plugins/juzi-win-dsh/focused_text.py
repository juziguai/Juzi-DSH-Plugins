"""Read focused UI Automation text without changing focus or clipboard."""
import json
import atexit
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from paste_text import POWERSHELL


class FocusReader:
    """One owned STA worker, one request at a time; never cache focused text."""
    def __init__(self, timeout=15):
        self.timeout = timeout
        self.lock = threading.Lock()
        self.process = None
        self.responses = None

    def _start(self):
        process = subprocess.Popen(
            [str(POWERSHELL), '-NoProfile', '-STA', '-NonInteractive', '-File',
             str(Path(__file__).with_suffix('.ps1'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', cwd=tempfile.gettempdir(),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        responses = queue.Queue()
        self.process, self.responses = process, responses

        def receive():
            try:
                while True:
                    line = process.stdout.readline(2 * 1024 * 1024 + 1)
                    if not line:
                        raise RuntimeError('UI Automation reader exited')
                    if len(line) > 2 * 1024 * 1024:
                        raise RuntimeError('UI Automation response exceeds limit')
                    responses.put(json.loads(line.lstrip('\ufeff')))
                    line = None
            except Exception as exc:
                responses.put(exc)
            finally:
                process.stdout.close()

        threading.Thread(target=receive, name='juzi-focus-reader', daemon=True).start()

    def _close(self):
        process, self.process = self.process, None
        self.responses = None
        if process is None:
            return
        try:
            process.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    def close(self):
        with self.lock:
            self._close()

    def read(self, hwnd, max_chars):
        with self.lock:
            try:
                if self.process is None:
                    self._start()
                self.process.stdin.write(json.dumps({'hwnd': hwnd, 'max_chars': max_chars}) + '\n')
                self.process.stdin.flush()
                response = self.responses.get(timeout=self.timeout)
                if isinstance(response, Exception):
                    raise response
                if not isinstance(response, dict) or not isinstance(response.get('ok'), bool):
                    raise RuntimeError('Invalid UI Automation response')
                return response
            except queue.Empty as exc:
                self._close()
                raise TimeoutError('UI Automation reader timed out') from exc
            except Exception:
                self._close()
                raise


_reader = FocusReader()
close = _reader.close
atexit.register(close)


def read(hwnd, max_chars=100000):
    return _reader.read(hwnd, max_chars)


def insertion_matches(before, after, text):
    normalize = lambda s: s.replace('\r\n', '\n').replace('\r', '\n').replace('\v', '\n').replace('\u2028', '\n')
    old, new, inserted = map(normalize, (before, after, text))
    if new == old:
        return False
    deleted = len(old) + len(inserted) - len(new)
    if deleted < 0 or deleted > len(old):
        return False
    prefix = 0
    while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
        prefix += 1
    suffix = 0
    while suffix < min(len(old), len(new)) and old[-suffix - 1] == new[-suffix - 1]:
        suffix += 1
    lower = max(0, len(new) - len(inserted) - suffix)
    upper = min(prefix, len(old) - deleted)
    if lower > upper:
        return False
    return new.find(inserted, lower, upper + len(inserted)) != -1


def verify_insertion(hwnd, before, text):
    if not before.get('ok') or before.get('truncated'):
        return False, 'baseline_unavailable'
    reason = 'content_not_observed'
    for delay in (0, 0.1, 0.2, 0.4):
        if delay:
            time.sleep(delay)
        try:
            after = read(hwnd)
        except Exception as exc:
            return False, str(exc)
        if after.get('error') in ('target_changed', 'password_control') or after.get('focus_id') != before.get('focus_id'):
            return False, 'target_changed'
        if after.get('ok') and not after.get('truncated') and insertion_matches(before['text'], after['text'], text):
            return True, None
        reason = after.get('error') or 'content_not_observed'
    return False, reason
