import ctypes
import threading
from ctypes import windll, c_uint, Structure, c_uint64, byref
from ctypes.wintypes import DWORD

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

windll.kernel32.GetTickCount64.restype = c_uint64
windll.kernel32.WTSGetActiveConsoleSessionId.restype = c_uint

_DESKTOP_READOBJECTS = 0x00000001


class _LASTINPUTINFO(Structure):
    _fields_ = [("cbSize", c_uint), ("dwTime", DWORD)]


def _format_duration(minutes: float) -> str:
    total_minutes = int(minutes)
    hours, mins = divmod(total_minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


_WINSTA_READATTRIBUTES = 0x00020000
_WINSTA_ACCESSGLOBALATOMS = 0x00000020


def _get_last_input_tick() -> int | None:
    """
    Read GetLastInputInfo from a thread explicitly attached to WinSta0\\Default.
    When running elevated via Task Scheduler the process sits in a service window
    station. OpenDesktopW("Default") without first switching to WinSta0 would open
    the service station's "Default" desktop whose input queue is never updated by
    user activity. Switching the thread to WinSta0 first makes the desktop open
    resolve to the interactive desktop and returns the real last-input tick.
    """
    result = [None]

    def _worker():
        h_winsta = windll.user32.OpenWindowStationW(
            "WinSta0", False, _WINSTA_READATTRIBUTES | _WINSTA_ACCESSGLOBALATOMS
        )
        if h_winsta:
            windll.user32.SetProcessWindowStation(h_winsta)
        h_desk = windll.user32.OpenDesktopW("Default", 0, False, _DESKTOP_READOBJECTS)
        if h_desk:
            windll.user32.SetThreadDesktop(h_desk)
            windll.user32.CloseDesktop(h_desk)
        if h_winsta:
            windll.user32.CloseWindowStation(h_winsta)
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            result[0] = int(lii.dwTime)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=1.0)
    return result[0]


def _get_idle_minutes() -> float | None:
    try:
        last_input_low = _get_last_input_tick()
        if last_input_low is None:
            return None
        tick64 = windll.kernel32.GetTickCount64()
        tick64_low = tick64 & 0xFFFFFFFF
        if tick64_low < last_input_low:
            idle_ms = (0x100000000 - last_input_low) + tick64_low
        else:
            idle_ms = tick64_low - last_input_low
        return idle_ms / 60_000
    except Exception as e:
        get_logger().warning("Failed to read idle time: %s", e)
        return None


class IdleMonitor(BaseMonitor):
    """Time since last keyboard or mouse input, read from the interactive desktop."""

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
