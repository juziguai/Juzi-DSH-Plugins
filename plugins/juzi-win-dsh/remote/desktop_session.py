"""Identify active Windows desktop sessions without relying on localized command output."""

import ctypes
import json
import os
from ctypes import wintypes


class SessionInfo(ctypes.Structure):
    _fields_ = [("id", wintypes.DWORD), ("station", wintypes.LPWSTR), ("state", ctypes.c_int)]


wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
wts.WTSFreeMemory.argtypes = [ctypes.c_void_p]
wts.WTSQuerySessionInformationW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD)
]
wts.WTSEnumerateSessionsW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(SessionInfo)), ctypes.POINTER(wintypes.DWORD)
]
kernel.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD


def current_session() -> int:
    number = wintypes.DWORD()
    if not kernel.ProcessIdToSessionId(os.getpid(), ctypes.byref(number)):
        raise ctypes.WinError(ctypes.get_last_error())
    return number.value


def _query(session: int, field: int):
    data = ctypes.c_void_p()
    size = wintypes.DWORD()
    if not wts.WTSQuerySessionInformationW(None, session, field, ctypes.byref(data), ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if field == 8:  # WTSConnectState
            return ctypes.cast(data, ctypes.POINTER(ctypes.c_int))[0]
        return ctypes.wstring_at(data) if data and size.value else ""
    finally:
        wts.WTSFreeMemory(data)


def is_active(session: int) -> bool:
    try:
        return session != 0 and _query(session, 8) == 0  # WTSActive
    except OSError:
        return False


def active_desktops() -> list[dict]:
    rows = ctypes.POINTER(SessionInfo)()
    count = wintypes.DWORD()
    if not wts.WTSEnumerateSessionsW(None, 0, 1, ctypes.byref(rows), ctypes.byref(count)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        desktops = []
        for index in range(count.value):
            row = rows[index]
            if row.id == 0 or row.state != 0:
                continue
            user = _query(row.id, 5)  # WTSUserName
            domain = _query(row.id, 7)  # WTSDomainName
            if user:
                desktops.append({"id": row.id, "account": f"{domain}\\{user}" if domain else user,
                                 "console": row.id == kernel.WTSGetActiveConsoleSessionId()})
        return desktops
    finally:
        wts.WTSFreeMemory(rows)


if __name__ == "__main__":
    print(json.dumps(active_desktops()))
