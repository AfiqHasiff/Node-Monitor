import ctypes
import psutil

from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class CpuMonitor(BaseMonitor):
    """
    CPU package temperature via LibreHardwareMonitorLib.dll (pythonnet).
    CPU usage % and real-time frequency via psutil.
    Requires the process to run as Administrator for AMD CPU temperature access.
    """

    def __init__(self, max_temp: float, max_usage: float, dll_path: str):
        super().__init__()
        self._max_temp = max_temp
        self._max_usage = max_usage
        self._dll_path = dll_path
        self._computer = None
        self._init_lhm()

    def _init_lhm(self) -> bool:
        if not _is_admin():
            get_logger().warning(
                "CPU temp requires Administrator privileges — "
                "run main.py as Administrator or via an elevated Task Scheduler entry."
            )
            return False
        try:
            import clr  # type: ignore
            clr.AddReference(self._dll_path)
            computer = __import__("LibreHardwareMonitor.Hardware", fromlist=["Computer"]).Computer()
            computer.IsCpuEnabled = True
            computer.Open()
            self._computer = computer
            return True
        except FileNotFoundError:
            get_logger().warning(
                "LHM DLL not found at '%s' — CPU temp will not be monitored. "
                "Update lhm_dll_path in config.yaml.",
                self._dll_path,
            )
        except Exception as e:
            get_logger().warning("Failed to initialise LHM — CPU temp will not be monitored: %s", e)
        return False

    def _collect_temp_sensors(self, hardware) -> list[tuple[str, float]]:
        results = []
        for sensor in hardware.Sensors:
            try:
                if "temperature" not in str(sensor.SensorType).lower():
                    continue
                if sensor.Value is None:
                    continue
                val = float(sensor.Value)
                if val > 0:
                    results.append((sensor.Name.lower(), val))
            except Exception:
                continue
        for sub in hardware.SubHardware:
            results.extend(self._collect_temp_sensors(sub))
        return results

    def _update_hardware(self, hardware) -> None:
        """Recursively update hardware and all sub-hardware."""
        hardware.Update()
        for sub in hardware.SubHardware:
            self._update_hardware(sub)

    def _read_cpu_temp(self) -> float | None:
        if self._computer is None:
            if not self._init_lhm():
                return None
        try:
            sensors = []
            for hardware in self._computer.Hardware:
                self._update_hardware(hardware)
                sensors.extend(self._collect_temp_sensors(hardware))

            if not sensors:
                return None

            for name, val in sensors:
                if "tctl" in name or "tdie" in name or "package" in name:
                    return val
            return max(val for _, val in sensors)
        except Exception as e:
            get_logger().warning("Failed to read CPU temp from LHM: %s", e)
            self._computer = None
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
