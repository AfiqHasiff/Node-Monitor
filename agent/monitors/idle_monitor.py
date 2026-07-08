from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger
from agent.monitors.session_monitor import query_wts_info_ex

_FILETIME_TO_SECONDS = 1e7  # 100-ns ticks per second


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
    Use LastInputTime and CurrentTime from WTSInfoEx (class 25).
    Both are kernel-side FILETIMEs sampled atomically at query time, so the
    difference is accurate regardless of window station or elevation context.
    Replaces GetLastInputInfo + desktop-switching which requires the calling
    process to be on the interactive window station to get a live input queue.
    """
    try:
        level1 = query_wts_info_ex()
        if level1 is None:
            return None
        idle_ticks = level1.CurrentTime - level1.LastInputTime
        if idle_ticks < 0:
            return None
        return idle_ticks / _FILETIME_TO_SECONDS / 60
    except Exception as e:
        get_logger().warning("Failed to read idle time: %s", e)
        return None


class IdleMonitor(BaseMonitor):
    """Time since last keyboard or mouse input via WTSInfoEx."""

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
