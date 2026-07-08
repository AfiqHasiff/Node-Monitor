import ctypes
from ctypes import windll, c_ulong, c_long, c_longlong, c_void_p, POINTER

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

_WTS_SESSION_INFO_EX = 25
_WTS_SESSIONSTATE_LOCK   = 0   # Windows 8+: 0 = locked
_WTS_SESSIONSTATE_UNLOCK = 1   # Windows 8+: 1 = unlocked

_wtsapi32 = windll.wtsapi32
_wtsapi32.WTSQuerySessionInformationW.restype = ctypes.c_bool
_wtsapi32.WTSQuerySessionInformationW.argtypes = [
    c_void_p, c_ulong, ctypes.c_uint, POINTER(c_void_p), POINTER(c_ulong),
]
_wtsapi32.WTSFreeMemory.restype = None
_wtsapi32.WTSFreeMemory.argtypes = [c_void_p]
windll.kernel32.WTSGetActiveConsoleSessionId.restype = c_ulong


class _WTSINFOEX_LEVEL1_W(ctypes.Structure):
    # Full SDK layout. The c_longlong fields give this struct 8-byte alignment,
    # which causes ctypes to insert 4 bytes of padding after the outer Level
    # field in _WTSINFOEXW — matching the Windows SDK memory layout.
    # Previously, the missing SessionState field and absent LARGE_INTEGER fields
    # meant no padding was inserted, so Python read SessionId bytes as SessionFlags
    # (typically 1), causing the lock check to always return True.
    _fields_ = [
        ("SessionId",               c_ulong),
        ("SessionState",            c_long),     # WTS_CONNECTSTATE_CLASS — was missing
        ("SessionFlags",            c_long),     # 0=locked, 1=unlocked on Windows 8+
        ("WinStationName",          ctypes.c_wchar * 33),
        ("UserName",                ctypes.c_wchar * 21),
        ("DomainName",              ctypes.c_wchar * 18),
        ("LogonTime",               c_longlong),
        ("ConnectTime",             c_longlong),
        ("DisconnectTime",          c_longlong),
        ("LastInputTime",           c_longlong),  # FILETIME of last user input
        ("CurrentTime",             c_longlong),  # FILETIME at query time
        ("IncomingBytes",           c_ulong),
        ("OutgoingBytes",           c_ulong),
        ("IncomingFrames",          c_ulong),
        ("OutgoingFrames",          c_ulong),
        ("IncomingCompressedBytes", c_ulong),
        ("OutgoingCompressedBytes", c_ulong),
    ]


class _WTSINFOEX_LEVEL_W(ctypes.Union):
    _fields_ = [("WTSInfoExLevel1", _WTSINFOEX_LEVEL1_W)]


class _WTSINFOEXW(ctypes.Structure):
    _fields_ = [
        ("Level", c_ulong),
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


def query_wts_info_ex() -> _WTSINFOEX_LEVEL1_W | None:
    """
    Query WTSInfoEx (class 25) for the active console session.
    Copies the buffer before freeing so callers own the returned struct.
    Works from any privilege level including elevated Task Scheduler processes.
    """
    try:
        session_id = _get_active_session_id()
        if session_id is None:
            return None

        buf = c_void_p()
        bytes_returned = c_ulong()
        ok = _wtsapi32.WTSQuerySessionInformationW(
            None, session_id, _WTS_SESSION_INFO_EX,
            ctypes.byref(buf), ctypes.byref(bytes_returned),
        )
        if not ok or not buf:
            return None

        raw = ctypes.string_at(buf.value, ctypes.sizeof(_WTSINFOEXW))
        _wtsapi32.WTSFreeMemory(buf)
        info = _WTSINFOEXW.from_buffer_copy(raw)
        return info.Data.WTSInfoExLevel1
    except Exception as e:
        get_logger().warning("Failed to query WTSInfoEx: %s", e)
        return None


def _is_session_locked() -> bool:
    level1 = query_wts_info_ex()
    if level1 is None:
        return False
    return level1.SessionFlags == _WTS_SESSIONSTATE_LOCK


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
