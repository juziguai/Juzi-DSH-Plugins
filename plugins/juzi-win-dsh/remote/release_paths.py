"""Paths shared by the SSH client and the release installer."""

import re
import subprocess
from pathlib import Path, PureWindowsPath


def release_root(value: str) -> str:
    path = PureWindowsPath(value)
    if (not path.is_absolute() or not re.fullmatch(r"[A-Za-z]:", path.drive)
            or len(path.parts) < 2 or ".." in path.parts
            or any(c in value for c in '\r\n\0"<>|?*')):
        raise ValueError("远端安装目录必须是本地磁盘上的绝对目录。")
    return str(path)


def ps_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def run_remote_ps(target: str, script: str, timeout: float) -> subprocess.CompletedProcess:
    if not target or target.startswith("-") or any(c.isspace() for c in target):
        raise ValueError("SSH 主机名无效。")
    command = ("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); "
               "$env:PSModulePath=[IO.Path]::Combine($PSHOME,'Modules')+';'+$env:PSModulePath;\n")
    command += Path(__file__).with_name("release_store.ps1").read_text(encoding="utf-8-sig") + "\n"
    command += "try { " + script + " } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={max(1, int(timeout))}",
         target, PS_STDIN_COMMAND],
        input=command, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout + 30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

PS_STDIN_COMMAND = (
    'powershell.exe -NoProfile -NonInteractive -Command '
    '"[Console]::InputEncoding=[Text.UTF8Encoding]::new(); '
    '& ([ScriptBlock]::Create([Console]::In.ReadToEnd()))"'
)


def release_selector(root: str, candidate: str | None) -> str:
    if candidate is not None and not re.fullmatch("[0-9a-f]{32}", candidate):
        raise ValueError("无效的发布编号。")
    source = ps_string(candidate) if candidate else "[IO.File]::ReadAllText((Join-Path $store 'active-release')).Trim()"
    return (f"$store=Open-ReleaseStore {ps_string(release_root(root))}; $id={source}; "
            "if ($id -cnotmatch '^[0-9a-f]{32}$') { throw 'Invalid active release' }; "
            "$bundle=Join-Path $store $id; ")
