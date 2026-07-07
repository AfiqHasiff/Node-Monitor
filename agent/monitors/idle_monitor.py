import ctypes
from ctypes import Structure, windll, c_uint, c_uint64
from ctypes.wintypes import DWORD

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

windll.kernel32.GetTickCount64.restype = c_uint64


class _LASTINPUTINFO(Structure):
    _fields_ = [("cbSize", c_uint), ("dwTime", DWORD)]


def _format_duration(minutes: float) -> str:
    """Format a duration in minutes as a human-readable string."""
    total_minutes = int(minutes)
    hours, mins = divmod(total_minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


class IdleMonitor(BaseMonitor):
    """
    Time since last keyboard or mouse input via Win32 GetLastInputInfo.
    Uses GetTickCount64 to avoid the 49-day tick count overflow.
    """

    def __init__(self, threshold_minutes: float):
        super().__init__()
        self._threshold_minutes = threshold_minutes

    def _get_idle_minutes(self) -> float | None:
        try:
            lii = _LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
            if not windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                return None
            tick64 = windll.kernel32.GetTickCount64()
            last_input = lii.dwTime & 0xFFFFFFFF
            tick64_low = tick64 & 0xFFFFFFFF
            if tick64_low < last_input:
                idle_ms = (0x100000000 - last_input) + tick64_low
            else:
                idle_ms = tick64_low - last_input
            return idle_ms / 60_000
        except Exception as e:
            get_logger().warning("Failed to read idle time: %s", e)
            return None

    def read(self) -> list[MetricSnapshot]:
        idle_minutes = self._get_idle_minutes()
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
