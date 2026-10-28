"""Read focused UI Automation text without changing focus or clipboard."""
import json
import subprocess
import time
from pathlib import Path
from paste_text import POWERSHELL


def read(hwnd, max_chars=100000):
    result = subprocess.run(
        [str(POWERSHELL), '-NoProfile', '-STA', '-NonInteractive', '-File',
         str(Path(__file__).with_suffix('.ps1')), '-ExpectedHwnd', str(hwnd),
         '-MaxChars', str(max_chars)], capture_output=True, text=True,
        encoding='utf-8', timeout=15,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('UI Automation reader failed: ' + result.stderr[:300])
    return json.loads(result.stdout.lstrip('\ufeff'))


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
            reason = str(exc)
            continue
        if after.get('error') in ('target_changed', 'password_control') or after.get('focus_id') != before.get('focus_id'):
            return False, 'target_changed'
        if after.get('ok') and not after.get('truncated') and insertion_matches(before['text'], after['text'], text):
            return True, None
        reason = after.get('error') or 'content_not_observed'
    return False, reason
