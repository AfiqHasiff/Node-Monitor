import ctypes
from ctypes import windll, c_ulong, c_void_p, POINTER

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

# WTSSessionInfoEx returns WTSINFOEXW which has a SessionFlags field.
# WTF_SESSION_FLAG_LOCK_SESSION (0x00000001) is set when the session is locked.
_WTS_SESSION_INFO_EX = 25
_WTF_SESSION_FLAG_LOCK_SESSION = 0x00000001

_wtsapi32 = windll.wtsapi32
_wtsapi32.WTSQuerySessionInformationW.restype = ctypes.c_bool
_wtsapi32.WTSQuerySessionInformationW.argtypes = [
    c_void_p, c_ulong, ctypes.c_uint, POINTER(c_void_p), POINTER(c_ulong),
]
_wtsapi32.WTSFreeMemory.restype = None
_wtsapi32.WTSFreeMemory.argtypes = [c_void_p]
windll.kernel32.WTSGetActiveConsoleSessionId.restype = c_ulong


class _WTSINFOEX_LEVEL1_W(ctypes.Structure):
    # WTSINFOEXW.Data.WTSInfoExLevel1 — only the first two fields are needed.
    # SessionId: ULONG, SessionFlags: ULONG (rest of the struct is not accessed)
    _fields_ = [
        ("SessionId",    ctypes.c_ulong),
        ("SessionFlags", ctypes.c_ulong),
    ]


class _WTSINFOEX_LEVEL_W(ctypes.Union):
    _fields_ = [("WTSInfoExLevel1", _WTSINFOEX_LEVEL1_W)]


class _WTSINFOEXW(ctypes.Structure):
    _fields_ = [
        ("Level", ctypes.c_ulong),
        ("Data",  _WTSINFOEX_LEVEL_W),
    ]


def _get_active_session_id() -> int | None:
    session_id = windll.kernel32.WTSGetActiveConsoleSessionId()
    return None if session_id == 0xFFFFFFFF else int(session_id)


def _get_active_username() -> str | None:
    try:
        import win32ts  # type: ignore
        session_id = _get_active_session_id()
        if session_id is None:
            return None
        username = win32ts.WTSQuerySessionInformation(
            win32ts.WTS_CURRENT_SERVER_HANDLE,
            session_id,
            win32ts.WTSUserName,
        )
        return username or None
    except Exception as e:
        get_logger().warning("Failed to read session username: %s", e)
        return None


def _is_session_locked() -> bool:
    """
    Query WTSSessionInfoEx (class 25) for the active console session.
    WTSINFOEXW.Data.WTSInfoExLevel1.SessionFlags has bit 0 set when locked.
    This API works from any session including elevated non-interactive services
    and does not rely on process enumeration.
    """
    try:
        session_id = _get_active_session_id()
        if session_id is None:
            return False

        buf = c_void_p()
        bytes_returned = c_ulong()
        ok = _wtsapi32.WTSQuerySessionInformationW(
            None, session_id, _WTS_SESSION_INFO_EX,
            ctypes.byref(buf), ctypes.byref(bytes_returned),
        )
        if not ok or not buf:
            return False

        info = ctypes.cast(buf, ctypes.POINTER(_WTSINFOEXW)).contents
        flags = info.Data.WTSInfoExLevel1.SessionFlags
        _wtsapi32.WTSFreeMemory(buf)
        return bool(flags & _WTF_SESSION_FLAG_LOCK_SESSION)
    except Exception as e:
        get_logger().warning("Failed to check lock state: %s", e)
        return False


class SessionMonitor(BaseMonitor):
    """Reports the logged-on Windows username and lock state."""

    def read(self) -> list[MetricSnapshot]:
        username = _get_active_username()
        locked = _is_session_locked()

        if username:
            display = f"{username} (Locked)" if locked else username
        else:
            display = "None"

        return [MetricSnapshot(
            label="Logged On",
            value=0,
            unit="",
            threshold=None,
            display_value=display,
        )]
