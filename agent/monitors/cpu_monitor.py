import psutil

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger


class CpuMonitor(BaseMonitor):
    """
    CPU package temperature via LibreHardwareMonitorLib.dll (pythonnet).
    CPU usage % and real-time frequency via psutil.
    """

    def __init__(self, max_temp: float, max_usage: float, dll_path: str):
        super().__init__()
        self._max_temp = max_temp
        self._max_usage = max_usage
        self._dll_path = dll_path
        self._computer = None
        self._lhm = None
        self._init_lhm()

    def _init_lhm(self) -> bool:
        """Load the LHM DLL and open the computer object. Returns True on success."""
        try:
            import clr  # type: ignore  # pythonnet
            clr.AddReference(self._dll_path)
            from LibreHardwareMonitor.Hardware import Computer  # type: ignore
            self._lhm = __import__("LibreHardwareMonitor.Hardware", fromlist=["Hardware"])
            computer = Computer()
            computer.IsCpuEnabled = True
            computer.Open()
            self._computer = computer
            return True
        except FileNotFoundError:
            get_logger().warning(
                "LHM DLL not found at '%s' — CPU temp will not be monitored. "
                "Update lhm_dll_path in config.yaml to point to LibreHardwareMonitorLib.dll.",
                self._dll_path,
            )
        except Exception as e:
            get_logger().warning("Failed to initialise LHM — CPU temp will not be monitored: %s", e)
        return False

    def _read_cpu_temp(self) -> float | None:
        if self._computer is None:
            if not self._init_lhm():
                return None

        try:
            temps = []
            for hardware in self._computer.Hardware:
                hardware.Update()
                for sensor in hardware.Sensors:
                    if (
                        sensor.SensorType == self._lhm.SensorType.Temperature
                        and sensor.Value is not None
                    ):
                        name = sensor.Name.lower()
                        # Prefer the package sensor; collect all temp sensors as fallback
                        if "package" in name:
                            return float(sensor.Value)
                        temps.append(float(sensor.Value))
            return max(temps) if temps else None
        except Exception as e:
            get_logger().warning("Failed to read CPU temp from LHM: %s", e)
            self._computer = None  # Reset so next poll retries
            return None

    def _read_cpu_freq_ghz(self) -> float | None:
        try:
            freq = psutil.cpu_freq()
            return round(freq.current / 1000, 1) if freq else None
        except Exception:
            return None

    def read(self) -> list[MetricSnapshot]:
        snapshots = []

        temp = self._read_cpu_temp()
        if temp is not None:
            snapshots.append(MetricSnapshot(
                label="CPU Temp",
                value=round(temp, 1),
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
