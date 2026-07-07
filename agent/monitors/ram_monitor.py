import psutil

from agent.base_monitor import BaseMonitor, MetricSnapshot


class RamMonitor(BaseMonitor):
    """Reports RAM usage. No alerts — status reporting only."""

    def read(self) -> list[MetricSnapshot]:
        mem = psutil.virtual_memory()
        used_gb = round(mem.used / (1024 ** 3), 1)
        total_gb = round(mem.total / (1024 ** 3), 1)
        pct = mem.percent
        return [MetricSnapshot(
            label="RAM Usage",
            value=pct,
            unit="%",
            threshold=None,
            display_value=f"{used_gb} / {total_gb}GB ({pct}%)",
        )]
