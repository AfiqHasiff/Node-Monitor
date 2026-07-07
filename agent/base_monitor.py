from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class MetricSnapshot:
    """A single reading from a monitor at a point in time."""
    label: str
    value: float
    unit: str
    threshold: float | None = None
    alert_triggered: bool = False


class BaseMonitor(ABC):
    """All monitors implement this interface so the main loop stays unchanged."""

    def __init__(self) -> None:
        self._alert_active: dict[str, bool] = {}

    @abstractmethod
    def read(self) -> list[MetricSnapshot]:
        """Return current metric snapshots."""
        ...

    def check_alerts(self, snapshots: list[MetricSnapshot]) -> list[MetricSnapshot]:
        """Rising-edge alert detection: fires once when threshold is crossed, resets when it drops back."""
        triggered = []
        for s in snapshots:
            if s.threshold is None or s.threshold == 0:
                continue
            currently_over = s.value > s.threshold
            was_active = self._alert_active.get(s.label, False)

            if currently_over and not was_active:
                s.alert_triggered = True
                self._alert_active[s.label] = True
                triggered.append(s)
            elif not currently_over and was_active:
                self._alert_active[s.label] = False

        return triggered

    def reset_alert(self, label: str) -> None:
        self._alert_active[label] = False
