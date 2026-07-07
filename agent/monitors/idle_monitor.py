import ctypes
from ctypes import windll, c_ulong, c_void_p, c_int64, POINTER

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

# WTSSessionInfo (24) returns WTSINFOW which contains LastInputTime and CurrentTime
_WTS_SESSION_INFO = 24

_wtsapi32 = windll.wtsapi32
_wtsapi32.WTSQuerySessionInformationW.restype = ctypes.c_bool
_wtsapi32.WTSQuerySessionInformationW.argtypes = [
    c_void_p, c_ulong, ctypes.c_uint, POINTER(c_void_p), POINTER(c_ulong),
]
_wtsapi32.WTSFreeMemory.restype = None
_wtsapi32.WTSFreeMemory.argtypes = [c_void_p]
windll.kernel32.WTSGetActiveConsoleSessionId.restype = c_ulong


class _WTSINFOW(ctypes.Structure):
    # Layout matches wtsapi32.h WTSINFOW — natural alignment, no explicit packing.
    # WINSTATIONNAME_LENGTH=32, DOMAIN_LENGTH+1=18, USERNAME_LENGTH+1=21
    # LARGE_INTEGER fields are 8-byte aligned; ctypes inserts 2 bytes padding after
    # UserName (ends at offset 174) to reach the next 8-byte boundary at 176.
    _fields_ = [
        ("State",                   ctypes.c_ulong),
        ("SessionId",               ctypes.c_ulong),
        ("IncomingBytes",           ctypes.c_ulong),
        ("OutgoingBytes",           ctypes.c_ulong),
        ("IncomingFrames",          ctypes.c_ulong),
        ("OutgoingFrames",          ctypes.c_ulong),
        ("IncomingCompressedBytes", ctypes.c_ulong),
        ("OutgoingCompressedBytes", ctypes.c_ulong),
        ("WinStationName",          ctypes.c_wchar * 32),
        ("Domain",                  ctypes.c_wchar * 18),
        ("UserName",                ctypes.c_wchar * 21),
        ("ConnectTime",             c_int64),
        ("DisconnectTime",          c_int64),
        ("LastInputTime",           c_int64),
        ("LogonTime",               c_int64),
        ("CurrentTime",             c_int64),
    ]


def _format_duration(minutes: float) -> str:
    total_minutes = int(minutes)
    hours, mins = divmod(total_minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _get_idle_minutes() -> float | None:
    try:
        session_id = windll.kernel32.WTSGetActiveConsoleSessionId()
        if session_id == 0xFFFFFFFF:
            return None

        buf = c_void_p()
        bytes_returned = c_ulong()
        ok = _wtsapi32.WTSQuerySessionInformationW(
            None, session_id, _WTS_SESSION_INFO,
            ctypes.byref(buf), ctypes.byref(bytes_returned),
        )
        if not ok or not buf:
            return None

        info = ctypes.cast(buf, ctypes.POINTER(_WTSINFOW)).contents
        last_input = info.LastInputTime
        current = info.CurrentTime
        _wtsapi32.WTSFreeMemory(buf)

        if last_input <= 0 or current <= 0:
            return None
        idle_100ns = current - last_input
        if idle_100ns < 0:
            return None
        return idle_100ns / (10_000_000 * 60)  # 100ns intervals → minutes
    except Exception as e:
        get_logger().warning("Failed to read idle time: %s", e)
        return None


class IdleMonitor(BaseMonitor):
    """
    Time since last keyboard or mouse input via WTSQuerySessionInformationW.
    Session-aware — works correctly from elevated and background processes.
    """

    def __init__(self, threshold_minutes: float):
        super().__init__()
        self._threshold_minutes = threshold_minutes

    def read(self) -> list[MetricSnapshot]:
        idle_minutes = _get_idle_minutes()
        if idle_minutes is None:
            return []

        current_str = _format_duration(idle_minutes)
        threshold_str = _format_duration(self._threshold_minutes) if self._threshold_minutes else ""

        return [MetricSnapshot(
            label="Idle Time",
            value=round(idle_minutes, 1),
            unit="min",
            threshold=self._threshold_minutes,
            display_value=current_str,
            threshold_display=threshold_str,
        )]
