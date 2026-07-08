import ctypes
from ctypes import windll, c_uint, c_uint64, Structure
from ctypes.wintypes import DWORD

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

windll.kernel32.GetTickCount64.restype = c_uint64


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


def _get_idle_minutes() -> float | None:
    """
    GetLastInputInfo returns a 32-bit tick counter. GetTickCount64 is used for
    the current tick to handle the 49-day rollover correctly.
    This call works from an elevated interactive session (Task Scheduler with
    'Run only when user is logged on'). It does NOT work from session-0 services.
    """
    try:
        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        tick64 = windll.kernel32.GetTickCount64()
        last_low = int(lii.dwTime)
        now_low = tick64 & 0xFFFFFFFF
        if now_low < last_low:
            idle_ms = (0x100000000 - last_low) + now_low
        else:
            idle_ms = now_low - last_low
        return idle_ms / 60_000
    except Exception as e:
        get_logger().warning("Failed to read idle time: %s", e)
        return None


class IdleMonitor(BaseMonitor):
    """Time since last keyboard or mouse input."""

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
