#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR 引擎编排与文字命中计算。

优先 Windows.Media.Ocr（系统语言包，免下载）；不可用时回退已安装的 Tesseract。
对调用方只返回词框与匹配结果，不保存整张截图。
"""

from __future__ import annotations

import atexit
import csv
import io
import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WINDOWS_OCR_SCRIPT = SCRIPT_DIR / "ocr_windows.ps1"
POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
TESSERACT_CANDIDATES = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"D:\Tools\Tesseract-OCR\tesseract.exe"),
)
OCR_UNAVAILABLE_HINT = (
    "未找到可用的 OCR 引擎。请启用 Windows 中文(简体) OCR 语言组件"
    "（设置 → 时间和语言 → 语言 → 中文(简体) → 可选功能 → 光学字符识别），"
    "或安装 Tesseract 5 并放置 chi_sim/eng 语言数据；详见 README。"
)
MAX_OCR_RESPONSE_BYTES = 16 * 1024 * 1024


def _windows_lang_tag(lang: str) -> str:
    value = (lang or "").lower()
    if "chi_sim" in value or "zh" in value:
        return "zh-Hans-CN"
    if "eng" in value or "en" in value:
        return "en-US"
    return lang or "zh-Hans-CN"


class OcrWorker:
    """常驻 STA PowerShell WinRT OCR 子进程：首次启动加载程序集，后续复用避免 5~6 秒冷启动。"""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.responses: queue.Queue[Any] | None = None

    def _start(self) -> None:
        process = subprocess.Popen(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-STA",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(WINDOWS_OCR_SCRIPT),
                "-Worker",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=tempfile.gettempdir(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        responses: queue.Queue[Any] = queue.Queue()
        self.process, self.responses = process, responses

        def receive() -> None:
            assert process.stdout is not None
            try:
                while True:
                    line = process.stdout.readline(MAX_OCR_RESPONSE_BYTES + 1)
                    if not line:
                        raise RuntimeError("Windows OCR worker exited")
                    if len(line) > MAX_OCR_RESPONSE_BYTES:
                        raise RuntimeError("Windows OCR response exceeds limit")
                    stripped = line.lstrip("\ufeff").strip()
                    if not stripped:
                        continue
                    responses.put(json.loads(stripped))
            except Exception as exc:  # noqa: BLE001
                responses.put(exc)
            finally:
                try:
                    process.stdout.close()
                except OSError:
                    pass

        threading.Thread(target=receive, name="juzi-ocr-worker", daemon=True).start()

    def _close(self) -> None:
        process, self.process = self.process, None
        self.responses = None
        if process is None:
            return
        try:
            if process.stdin is not None:
                process.stdin.close()
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass

    def close(self) -> None:
        with self.lock:
            self._close()

    def recognize_path(self, path: Path, lang_tag: str) -> dict[str, Any]:
        return self.request({"path": str(path), "lang_tag": lang_tag})

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            try:
                if self.process is None or self.process.poll() is not None:
                    self._close()
                    self._start()
                assert self.process is not None and self.process.stdin is not None and self.responses is not None
                self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
                response = self.responses.get(timeout=self.timeout)
                if isinstance(response, Exception):
                    raise response
                if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
                    raise RuntimeError("Invalid Windows OCR worker response")
                return response
            except queue.Empty as exc:
                self._close()
                raise TimeoutError("Windows OCR worker timed out") from exc
            except Exception:
                self._close()
                raise


_ocr_worker = OcrWorker()
close = _ocr_worker.close
atexit.register(close)


def _run_powershell(path: Path, lang_tag: str) -> dict[str, Any]:
    return _ocr_worker.recognize_path(path, lang_tag)


def capture_window_png(hwnd: int, frame: dict[str, int], area: dict[str, int]) -> bytes:
    """Capture only the requested WGC window. Both rectangles use physical screen pixels."""
    with tempfile.TemporaryDirectory(prefix=".tmp-juzi-wgc-") as directory:
        path = Path(directory) / "frame.png"
        path.touch()
        result = _ocr_worker.request({
            "operation": "capture_window", "hwnd": hwnd, "path": str(path),
            "frame_width": frame["width"], "frame_height": frame["height"],
            "x": area["x"] - frame["x"], "y": area["y"] - frame["y"],
            "width": area["width"], "height": area["height"],
        })
        if not result["ok"]:
            raise RuntimeError(result.get("message") or "Windows Graphics Capture failed")
        return path.read_bytes()


def _write_temp_png(png_bytes: bytes) -> Path:
    handle, name = tempfile.mkstemp(prefix=".tmp-juzi-ocr-", suffix=".png")
    with os.fdopen(handle, "wb") as stream:
        stream.write(png_bytes)
    return Path(name)


def _windows_ocr(png_bytes: bytes, lang: str) -> dict[str, Any]:
    if not WINDOWS_OCR_SCRIPT.exists():
        return {"ok": False, "error": "ocr_unavailable", "message": "缺少 ocr_windows.ps1。"}
    path = _write_temp_png(png_bytes)
    try:
        payload = _run_powershell(path, _windows_lang_tag(lang))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "ocr_failed", "message": f"Windows OCR 调用失败：{exc}"}
    finally:
        try:
            path.unlink()
        except OSError:
            pass
    if (
        payload.get("ok")
        and "chi_sim" in (lang or "").lower()
        and not str(payload.get("lang") or "").lower().startswith("zh")
    ):
        return {
            "ok": False,
            "error": "ocr_unavailable",
            "message": f"Windows OCR 未安装中文识别语言包（当前识别语言：{payload.get('lang')}）。",
        }
    return payload


_TESSERACT_LANG_CACHE: dict[Path, set[str]] = {}


def _tesseract_binary() -> Path | None:
    found = shutil.which("tesseract")
    if found:
        return Path(found)
    for candidate in TESSERACT_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _tesseract_languages(binary: Path) -> set[str]:
    cached = _TESSERACT_LANG_CACHE.get(binary)
    if cached is not None:
        return cached
    try:
        completed = subprocess.run(
            [str(binary), "--list-langs"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:  # noqa: BLE001
        return set()
    lines = (completed.stdout or "").splitlines()
    langs = {line.strip() for line in lines if line.strip() and " " not in line and ":" not in line}
    if langs:
        _TESSERACT_LANG_CACHE[binary] = langs
    return langs


def _tesseract_ocr(png_bytes: bytes, lang: str) -> dict[str, Any]:
    binary = _tesseract_binary()
    if binary is None:
        return {"ok": False, "error": "ocr_unavailable", "message": "未安装 Tesseract。"}
    requested = [part for part in (lang or "").split("+") if part.strip()]
    available = _tesseract_languages(binary)
    usable = [part for part in requested if part in available]
    if not usable:
        return {
            "ok": False,
            "error": "ocr_unavailable",
            "message": f"Tesseract 缺少语言数据：需要 {requested}，已安装 {sorted(available)}。",
        }

    path = _write_temp_png(png_bytes)
    try:
        completed = subprocess.run(
            [str(binary), str(path), "stdout", "-l", "+".join(usable), "--psm", "6", "tsv"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        try:
            path.unlink()
        except OSError:
            pass
    if completed.returncode != 0:
        return {
            "ok": False,
            "error": "ocr_failed",
            "message": f"Tesseract 失败（exit={completed.returncode}）：{(completed.stderr or '').strip()[:400]}",
        }

    lines: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
    reader = csv.DictReader(io.StringIO(completed.stdout or ""), delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        if str(row.get("level", "")).strip() != "5":
            continue
        text = (row.get("text") or "").strip()
        if not text:
            continue
        try:
            confidence = float(row.get("conf") or -1)
            if confidence < 0:
                continue
            key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
            lines.setdefault(key, []).append(
                {
                    "text": text,
                    "x": int(float(row["left"])),
                    "y": int(float(row["top"])),
                    "w": int(float(row["width"])),
                    "h": int(float(row["height"])),
                    "conf": confidence,
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    rows = []
    for words in lines.values():
        rows.append({"text": " ".join(word["text"] for word in words), "words": words})
    return {"ok": True, "engine": "tesseract", "lang": "+".join(usable), "lines": rows}


def recognize(png_bytes: bytes, lang: str = "chi_sim+eng") -> dict[str, Any]:
    """Windows OCR 优先，失败再试 Tesseract；返回统一结构。"""
    windows = _windows_ocr(png_bytes, lang)
    if windows.get("ok"):
        return windows
    tesseract = _tesseract_ocr(png_bytes, lang)
    if tesseract.get("ok"):
        tesseract["fallback_from"] = windows.get("error") or "windows-ocr"
        return tesseract
    return {
        "ok": False,
        "error": "ocr_unavailable",
        "message": f"{windows.get('message') or ''} / {tesseract.get('message') or ''}".strip(" /"),
        "install_hint": OCR_UNAVAILABLE_HINT,
    }


def _overlap_ratio(first: dict[str, Any], second: dict[str, Any]) -> float:
    left = max(int(first["x"]), int(second["x"]))
    top = max(int(first["y"]), int(second["y"]))
    right = min(int(first["x"]) + int(first["w"]), int(second["x"]) + int(second["w"]))
    bottom = min(int(first["y"]) + int(first["h"]), int(second["y"]) + int(second["h"]))
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    smaller = min(int(first["w"]) * int(first["h"]), int(second["w"]) * int(second["h"]))
    return intersection / max(1, smaller)


def supplement_latin(png_bytes: bytes, lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
    """用 Tesseract eng 补 Windows OCR 漏掉的拉丁字符（如被光标遮住的字母）。

    Windows OCR 对中文字间分词与拉丁字偶有漏字；Tesseract 的拉丁词框若与
    Windows 词框重叠且更宽（例如 AB -> ABC），用更完整的那个替换，其余去重。
    """
    result = _tesseract_ocr(png_bytes, "eng")
    if not result.get("ok"):
        return lines, None
    merged = [
        dict(word)
        for line in lines
        for word in (line.get("words") or [])
        if str(word.get("text") or "").strip()
    ]
    for line in result.get("lines") or []:
        for extra in line.get("words") or []:
            extra_text = str(extra.get("text") or "").strip()
            if not extra_text:
                continue
            extra_ascii = all(ord(char) < 128 for char in extra_text)
            replaced = False
            for index, current in enumerate(merged):
                if _overlap_ratio(current, extra) < 0.35:
                    continue
                current_text = str(current.get("text") or "")
                current_ascii = all(ord(char) < 128 for char in current_text)
                if (
                    extra_ascii
                    and current_ascii
                    and int(extra["w"]) > int(current["w"]) + 4
                    and len(extra_text) >= len(current_text)
                ):
                    merged[index] = extra
                replaced = True
                break
            if not replaced:
                merged.append(extra)
    return [{"text": "", "words": merged}], "tesseract"


def _normalize(text: str) -> str:
    return "".join(char for char in text if not char.isspace()).lower()


def _row_segments(words: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """把 OCR 词框按视觉行聚合并按横向间隔切段。

    Windows OCR 常把同一行拆成多个 OcrLine（例如中文与拉丁字母分开），
    因此不能只按 OCR 的 line 分组；这里用词框的垂直重叠与水平间距重建视觉行。
    """
    if not words:
        return []
    heights = sorted(int(word["h"]) for word in words if int(word["h"]) > 0)
    median_height = heights[len(heights) // 2] if heights else 16
    gap_threshold = max(45, int(median_height * 2.5))

    ordered = sorted(words, key=lambda word: (int(word["y"]) + int(word["h"]) / 2.0, int(word["x"])))
    rows: list[list[dict[str, Any]]] = []
    row_bounds: list[tuple[float, float]] = []
    for word in ordered:
        top = float(word["y"])
        bottom = float(word["y"]) + float(word["h"])
        center = (top + bottom) / 2.0
        placed = False
        for index, (row_top, row_bottom) in enumerate(row_bounds):
            overlap = min(bottom, row_bottom) - max(top, row_top)
            if overlap >= 0.5 * min(bottom - top, row_bottom - row_top):
                rows[index].append(word)
                row_bounds[index] = (min(row_top, top), max(row_bottom, bottom))
                placed = True
                break
        if not placed:
            rows.append([word])
            row_bounds.append((top, bottom))

    segments: list[list[dict[str, Any]]] = []
    for row in rows:
        row.sort(key=lambda word: int(word["x"]))
        current: list[dict[str, Any]] = []
        last_right = None
        for word in row:
            if last_right is not None and int(word["x"]) - last_right > gap_threshold:
                if current:
                    segments.append(current)
                current = []
            current.append(word)
            last_right = int(word["x"]) + int(word["w"])
        if current:
            segments.append(current)
    return segments


def find_matches(
    lines: list[dict[str, Any]],
    needle: str,
    match: str = "contains",
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """在 OCR 结果中找 needle；忽略中文 OCR 字间空格，并跨 OCR 行拼接同一视觉行。"""
    target = _normalize(needle)
    if not target:
        return []
    words = [
        word
        for line in lines
        for word in (line.get("words") or [])
        if str(word.get("text") or "").strip()
    ]
    results: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int, int]] = set()

    def append_hit(word_slice: list[dict[str, Any]], hit_text: str) -> None:
        if not word_slice:
            return
        left = min(int(word["x"]) for word in word_slice)
        top = min(int(word["y"]) for word in word_slice)
        right = max(int(word["x"]) + int(word["w"]) for word in word_slice)
        bottom = max(int(word["y"]) + int(word["h"]) for word in word_slice)
        key = (left, top, right - left, bottom - top)
        if key in seen:
            return
        seen.add(key)
        confidences = [float(word["conf"]) for word in word_slice if "conf" in word]
        results.append(
            {
                "text": hit_text,
                "confidence": round(sum(confidences) / len(confidences) / 100.0, 4) if confidences else None,
                "rect": {"x": left, "y": top, "width": right - left, "height": bottom - top},
                "cx": int(round((left + right) / 2.0)),
                "cy": int(round((top + bottom) / 2.0)),
            }
        )

    for segment in _row_segments(words):
        normalized_chars: list[str] = []
        owner: list[int] = []
        for index, word in enumerate(segment):
            for char in _normalize(str(word.get("text") or "")):
                normalized_chars.append(char)
                owner.append(index)
        haystack = "".join(normalized_chars)
        if not haystack:
            continue

        if match == "exact":
            if haystack == target:
                append_hit(segment, needle)
            else:
                for word in segment:
                    if _normalize(str(word.get("text") or "")) == target:
                        append_hit([word], str(word.get("text") or ""))
        else:
            start = haystack.find(target)
            while start != -1 and len(results) < max_results:
                end = start + len(target)
                first, last = owner[start], owner[end - 1]
                append_hit(segment[first:last + 1], needle)
                start = haystack.find(target, end)
        if len(results) >= max_results:
            break

    results.sort(key=lambda item: (item["rect"]["y"], item["rect"]["x"]))
    return results[:max_results]


def _join_segment_words(segment: list[dict[str, Any]]) -> str:
    """把同一视觉段的 OCR 词合并为自然文本：中文字间不加多余空格，英文/数字词间保留空格。"""
    parts: list[str] = []
    for word in segment:
        token = str(word.get("text") or "").strip()
        if not token:
            continue
        if not parts:
            parts.append(token)
            continue
        prev = parts[-1]
        prev_ascii = ord(prev[-1]) < 128 and (prev[-1].isalnum() or prev[-1] in ".,:;+-/_")
        curr_ascii = ord(token[0]) < 128 and (token[0].isalnum() or token[0] in ".,:;+-/_")
        if prev_ascii and curr_ascii:
            parts.append(" ")
        parts.append(token)
    return "".join(parts)


def extract_text_blocks(
    lines: list[dict[str, Any]],
    max_items: int = 150,
) -> list[dict[str, Any]]:
    """把 OCR 词框重建为按阅读顺序排列的文本块及中心点坐标，供免截图快速读屏。"""
    words = [
        word
        for line in lines
        for word in (line.get("words") or [])
        if str(word.get("text") or "").strip()
    ]
    blocks: list[dict[str, Any]] = []
    for segment in _row_segments(words):
        text = _join_segment_words(segment)
        if not text:
            continue
        left = min(int(word["x"]) for word in segment)
        top = min(int(word["y"]) for word in segment)
        right = max(int(word["x"]) + int(word["w"]) for word in segment)
        bottom = max(int(word["y"]) + int(word["h"]) for word in segment)
        blocks.append(
            {
                "text": text,
                "rect": {"x": left, "y": top, "width": right - left, "height": bottom - top},
                "cx": int(round((left + right) / 2.0)),
                "cy": int(round((top + bottom) / 2.0)),
            }
        )
    blocks.sort(key=lambda item: (item["rect"]["y"], item["rect"]["x"]))
    return blocks[:max_items]
