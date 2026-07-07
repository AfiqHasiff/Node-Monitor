import psutil

from agent.base_monitor import BaseMonitor, MetricSnapshot


class RamMonitor(BaseMonitor):
    """Reports RAM usage percentage. No alerts — status reporting only."""

    def read(self) -> list[MetricSnapshot]:
        usage = psutil.virtual_memory().percent
        return [MetricSnapshot(
            label="RAM Usage",
            value=usage,
            unit="%",
            threshold=None,
        )]

    def check_alerts(self, snapshots: list[MetricSnapshot]) -> list[MetricSnapshot]:
        return []
