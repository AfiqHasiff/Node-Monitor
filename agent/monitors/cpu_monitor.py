import psutil

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger

_LHM_NAMESPACE = "root\\LibreHardwareMonitor"
_LHM_QUERY = "SELECT Name, Value, SensorType FROM Sensor WHERE SensorType='Temperature' AND Parent LIKE '%cpu%'"


class CpuMonitor(BaseMonitor):
    """
    CPU package temperature via LibreHardwareMonitor WMI bridge (falls back gracefully).
    CPU usage % and real-time frequency via psutil.
    """

    def __init__(self, max_temp: float, max_usage: float):
        super().__init__()
        self._max_temp = max_temp
        self._max_usage = max_usage
        self._wmi = None
        self._init_wmi()

    def _init_wmi(self) -> None:
        try:
            import wmi  # type: ignore
            self._wmi = wmi.WMI(namespace=_LHM_NAMESPACE)
        except Exception as e:
            get_logger().warning("LHM WMI bridge unavailable — CPU temp will not be monitored: %s", e)

    def _read_cpu_temp(self) -> float | None:
        if self._wmi is None:
            return None
        try:
            sensors = self._wmi.query(_LHM_QUERY)
            package = [s for s in sensors if "package" in s.Name.lower()]
            candidates = package if package else sensors
            if not candidates:
                return None
            return max(float(s.Value) for s in candidates)
        except Exception as e:
            get_logger().warning("Failed to read CPU temp from LHM: %s", e)
            return None

    def _read_cpu_freq_ghz(self) -> float | None:
        try:
            freq = psutil.cpu_freq()
            if freq is None:
                return None
            return round(freq.current / 1000, 1)
        except Exception:
            return None

    def read(self) -> list[MetricSnapshot]:
        snapshots = []

        temp = self._read_cpu_temp()
        if temp is not None:
            snapshots.append(MetricSnapshot(
                label="CPU Temp",
                value=temp,
                unit="°C",
                threshold=self._max_temp,
            ))

        usage = psutil.cpu_percent(interval=None)
        freq_ghz = self._read_cpu_freq_ghz()
        display = f"{usage}% @ {freq_ghz}GHz" if freq_ghz is not None else f"{usage}%"
        snapshots.append(MetricSnapshot(
            label="CPU Usage",
            value=usage,
            unit="%",
            threshold=self._max_usage,
            display_value=display,
        ))

        return snapshots
