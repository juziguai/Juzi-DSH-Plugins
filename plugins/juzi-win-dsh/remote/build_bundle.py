#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键离线构建远端免安装绿色便携包（`remote/bundle/`）。

不依赖外网或 GitHub：直接从本机 Python 运行时提取最小嵌入式绿色环境（标准库打包为
`pythonXY.zip` + 必需扩展 DLLs + `Pillow` 二进制包 + `_pth` 隔离路径配置），并打入完整
`juzi-win-dsh` 代码与 `remote/` 守护脚本，随后在无外部环境变量的纯净隔离模式下自动验收。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REMOTE_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = REMOTE_DIR.parent
BUNDLE_DIR = REMOTE_DIR / "bundle"

STDLIB_SKIP_DIRS = {
    "__pycache__",
    "site-packages",
    "test",
    "tests",
    "idlelib",
    "tkinter",
    "turtledemo",
    "ensurepip",
    "venv",
    "pydoc_data",
    "lib2to3",
}

DLL_SKIP_PREFIXES = ("_tkinter", "tcl8", "tk8", "zlib1")


def _copy_clean_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".tmp-*", "*.bak*"),
    )


def build_portable_python(base_prefix: Path, pil_dir: Path, out_py_dir: Path) -> str:
    out_py_dir.mkdir(parents=True, exist_ok=True)
    ver_tag = f"python{sys.version_info.major}{sys.version_info.minor}"

    # 1. Copy core executables and runtime DLLs
    core_files = [
        "python.exe",
        "pythonw.exe",
        "python3.dll",
        f"{ver_tag}.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "LICENSE.txt",
    ]
    for name in core_files:
        src = base_prefix / name
        if src.is_file():
            shutil.copy2(src, out_py_dir / name)

    # 2. Copy extension .pyd / .dll from DLLs (skip heavy GUI/Tkinter DLLs)
    src_dlls = base_prefix / "DLLs"
    dst_dlls = out_py_dir / "DLLs"
    dst_dlls.mkdir(parents=True, exist_ok=True)
    if src_dlls.is_dir():
        for item in src_dlls.iterdir():
            if item.is_file() and item.suffix.lower() in (".pyd", ".dll"):
                if any(item.name.lower().startswith(p) for p in DLL_SKIP_PREFIXES):
                    continue
                shutil.copy2(item, dst_dlls / item.name)

    # 3. Pack pure standard library into pythonXY.zip (official Windows embeddable style)
    stdlib_dir = base_prefix / "Lib"
    zip_path = out_py_dir / f"{ver_tag}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(stdlib_dir):
            rel_root = Path(root).relative_to(stdlib_dir)
            dirs[:] = [d for d in dirs if d not in STDLIB_SKIP_DIRS]
            for fname in files:
                if fname.endswith((".pyc", ".pyo")):
                    continue
                full = Path(root) / fname
                arcname = str(rel_root / fname) if str(rel_root) != "." else fname
                zf.write(full, arcname)

    # 4. Copy Pillow into portable site-packages
    sp_dir = out_py_dir / "site-packages"
    sp_dir.mkdir(parents=True, exist_ok=True)
    _copy_clean_tree(pil_dir, sp_dir / "PIL")
    # Copy Pillow.libs if present alongside PIL
    pil_libs = pil_dir.parent / "Pillow.libs"
    if pil_libs.is_dir():
        _copy_clean_tree(pil_libs, sp_dir / "Pillow.libs")

    # 5. Write strict isolated pythonXY._pth so target PC ignores any broken global PYTHONPATH
    pth_file = out_py_dir / f"{ver_tag}._pth"
    pth_content = "\n".join([
        f"{ver_tag}.zip",
        "DLLs",
        "site-packages",
        "../app",
        "../app/src",
        "../app/remote",
        "",
    ])
    pth_file.write_text(pth_content, encoding="utf-8")
    return ver_tag


def build_app_files(out_app_dir: Path) -> None:
    out_app_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PLUGIN_ROOT / "server.py", out_app_dir / "server.py")
    shutil.copy2(PLUGIN_ROOT / "requirements.txt", out_app_dir / "requirements.txt")
    _copy_clean_tree(PLUGIN_ROOT / "src", out_app_dir / "src")
    _copy_clean_tree(PLUGIN_ROOT / "scripts", out_app_dir / "scripts")

    rem_dst = out_app_dir / "remote"
    rem_dst.mkdir(parents=True, exist_ok=True)
    for fname in ("session1_daemon.py", "desktop_session.py", "ensure_daemon.ps1", "private_state.ps1", "build_bundle.py"):
        shutil.copy2(REMOTE_DIR / fname, rem_dst / fname)


def verify_bundle(bundle_dir: Path) -> dict[str, object]:
    py_exe = bundle_dir / "python" / "python.exe"
    srv_py = bundle_dir / "app" / "server.py"
    clean_env = {
        "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
        "TEMP": os.environ.get("TEMP", r"C:\Windows\Temp"),
        "TMP": os.environ.get("TMP", r"C:\Windows\Temp"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    proc = subprocess.Popen(
        [str(py_exe), "-u", str(srv_py)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=clean_env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "bundle-verifier", "version": "1.0"},
            },
        }
        requests = [init_msg, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}]
        output, err = proc.communicate("".join(json.dumps(req) + "\n" for req in requests), timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise RuntimeError("便携包隔离验证超时。")
    if proc.returncode:
        raise RuntimeError(f"便携包隔离验证失败：{err[:400]}")
    r1, r2 = map(json.loads, output.splitlines())

    tools = r2["result"]["tools"]
    return {
        "server_info": r1["result"]["serverInfo"],
        "tool_count": len(tools),
    }


def dir_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)


def main(output_dir: Path | None = None) -> int:
    import PIL

    output_dir = output_dir or BUNDLE_DIR
    t0 = time.monotonic()
    base_prefix = Path(sys.base_prefix).resolve()
    pil_dir = Path(PIL.__file__).resolve().parent

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ver_tag = build_portable_python(base_prefix, pil_dir, output_dir / "python")
    build_app_files(output_dir / "app")
    check = verify_bundle(output_dir)

    manifest = {
        "bridge_protocol": 2,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "python": sys.version.split()[0],
        "python_tag": ver_tag,
        "pillow": PIL.__version__,
        "verified_server": check["server_info"],
        "verified_tools": check["tool_count"],
        "bundle_size_mb": dir_size_mb(output_dir),
    }
    (output_dir / "VERSION.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    elapsed = round(time.monotonic() - t0, 2)
    print(f"BUNDLE_READY ({elapsed}s): {output_dir}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--verify-existing":
        print(json.dumps(verify_bundle(Path(sys.argv[2]).resolve())))
        raise SystemExit(0)
    raise SystemExit(main())
