#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建并同步 `juzi-win-dsh` 绿色便携运行包至远端 SSH Windows 主机。

职责边界：
1. 调用 `build_bundle.py` 生成并通过本机纯净隔离自检（或通过 `--skip-build` 复用现有 `remote/bundle/`）。
2. 将 `remote/bundle/` 压缩为临时归档 （每次构建独占）（退出时自动清理）。
3. 通过系统标准 `scp` 与 `ssh` + Windows 内置 `tar` 解压同步至远端目录，并校验远端 `VERSION.json`；
   可选 `--verify-bridge` 复用 `local_proxy.RemoteBridgeClient` 完成一次只读端到端健康检查。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any
from release_paths import ps_string, release_root, release_selector, run_remote_ps

REMOTE_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = REMOTE_DIR / "bundle"


def pack_bundle_zip(bundle_dir: Path, zip_path: Path) -> float:
    version_file = bundle_dir / "VERSION.json"
    if not version_file.is_file():
        raise FileNotFoundError(f"未找到便携包构建清单，请先构建：{version_file}")

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(bundle_dir):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "runtime")]
            rel_root = Path(root).relative_to(bundle_dir)
            for fname in files:
                if fname.endswith((".pyc", ".pyo", ".tmp")):
                    continue
                full = Path(root) / fname
                arcname = (rel_root / fname).as_posix() if str(rel_root) != "." else fname
                zf.write(full, arcname)

    return round(zip_path.stat().st_size / (1024 * 1024), 2)


def _checked(result: subprocess.CompletedProcess, operation: str) -> str:
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{operation}失败：{detail[:400]}")
    return result.stdout.strip()


def sync_to_host(
    ssh_target: str,
    zip_path: Path,
    remote_root: str,
    connect_timeout: float = 10.0,
    verify_bridge: bool = False,
) -> dict[str, Any]:
    root = release_root(remote_root)
    with zipfile.ZipFile(zip_path) as archive:
        manifest = json.loads(archive.read("VERSION.json"))
    if manifest.get("bridge_protocol") != 2:
        raise ValueError("便携包使用旧版远程协议，请重新构建。")
    with zip_path.open("rb") as source:
        checksum = hashlib.file_digest(source, "sha256").hexdigest()
    release = uuid.uuid4().hex
    select = release_selector(root, release)
    prepare = (f"$store=Open-ReleaseStore {ps_string(root)} -Create; "
               f"New-Item -ItemType Directory -Path (Join-Path $store '{release}') | Out-Null")
    _checked(run_remote_ps(ssh_target, prepare, connect_timeout), "准备独立版本目录")
    remote_zip = root.replace("\\", "/") + f"/releases/{release}/upload.zip"
    uploaded = subprocess.run(
        ["scp", "-B", "-o", f"ConnectTimeout={max(1, int(connect_timeout))}",
         str(zip_path), f"{ssh_target}:{remote_zip}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=max(60, connect_timeout * 6), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    _checked(uploaded, "上传")
    unpack = (select + "$zip=Join-Path $bundle 'upload.zip'; "
              f"if ((Get-FileHash -LiteralPath $zip).Hash -ne '{checksum}') {{ throw 'Archive checksum mismatch' }}; "
              "& tar.exe -xf $zip -C $bundle; if ($LASTEXITCODE) { throw 'Archive extraction failed' }; "
              "Remove-Item -LiteralPath $zip; "
              "& (Join-Path $bundle 'python\\python.exe') (Join-Path $bundle 'app\\remote\\build_bundle.py') --verify-existing $bundle; "
              "if ($LASTEXITCODE) { throw 'Candidate MCP startup failed' }")
    actual = json.loads(_checked(run_remote_ps(ssh_target, unpack, connect_timeout), "候选版本自检"))
    if actual.get("server_info") != manifest.get("verified_server") or actual.get("tool_count") != manifest.get("verified_tools"):
        raise RuntimeError("候选版本 MCP 工具清单与构建清单不符。")
    result = {"ok": True, "ssh_target": ssh_target, "remote_root": root,
              "release": release, "manifest": manifest}
    if verify_bridge:
        from local_proxy import RemoteBridgeClient

        bridge = RemoteBridgeClient(ssh_target, remote_root=root, candidate_release=release,
                                    confirm_mode="always", connect_timeout=connect_timeout)
        try:
            resp = bridge.forward_tool_call(1, {"name": "manage_window", "arguments": {"action": "get_work_area"}})
            if "error" in resp:
                raise ValueError(resp["error"].get("message", "远端返回 JSON-RPC 错误。"))
            reply = resp.get("result", {})
            content = reply.get("content") or [{}]
            payload = json.loads(content[0].get("text", "{}"))
            if reply.get("isError") or payload.get("ok") is not True or not payload.get("screen"):
                result.update(ok=False, bridge_verified=False, error=payload.get("error_code") or "bridge_check_failed",
                              message=payload.get("message") or "候选版本未通过桌面桥接验收。")
                return result
            result.update(bridge_verified=True, remote_screen=payload["screen"])
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            result.update(ok=False, bridge_verified=False, error="invalid_bridge_response", message=str(exc))
            return result
        finally:
            bridge.close()
    _checked(run_remote_ps(ssh_target, select + "Publish-Release $store $id", connect_timeout), "切换活动版本")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and sync portable juzi-win-dsh bundle over SSH")
    parser.add_argument("--ssh-target", default="", help="SSH host alias or user@host (omit with --pack-only)")
    parser.add_argument("--remote-root", default=r"C:\ProgramData\RemoteWinMCP")
    parser.add_argument("--skip-build", action="store_true", help="Reuse existing remote/bundle without rebuilding")
    parser.add_argument("--pack-only", action="store_true", help="Only build and verify local archive packaging")
    parser.add_argument("--verify-bridge", action="store_true", help="Run read-only MCP bridge check after sync")
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    args = parser.parse_args()

    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="juzi-win-release-") as temp_dir:
        bundle_dir = BUNDLE_DIR
        if not args.skip_build:
            import build_bundle

            if not args.pack_only:
                bundle_dir = Path(temp_dir) / "bundle"
            build_bundle.main(bundle_dir)
        tmp_zip = Path(temp_dir) / "bundle.zip"
        zip_mb = pack_bundle_zip(bundle_dir, tmp_zip)
        if args.pack_only:
            print(json.dumps({
                "ok": True,
                "mode": "pack_only",
                "bundle_dir": str(BUNDLE_DIR),
                "archive_size_mb": zip_mb,
                "elapsed_s": round(time.monotonic() - t0, 2),
            }, ensure_ascii=False, indent=2))
            return 0

        if not args.ssh_target:
            parser.error("必须提供 --ssh-target，或使用 --pack-only 仅执行本地构建打包校验。")

        summary = sync_to_host(
            ssh_target=args.ssh_target,
            zip_path=tmp_zip,
            remote_root=args.remote_root,
            connect_timeout=args.connect_timeout,
            verify_bridge=args.verify_bridge,
        )
        summary["archive_size_mb"] = zip_mb
        summary["elapsed_s"] = round(time.monotonic() - t0, 2)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
