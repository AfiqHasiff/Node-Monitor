from agent.base_monitor import BaseMonitor, MetricSnapshot
from agent.logger import get_logger


class GpuMonitor(BaseMonitor):
    """
    NVIDIA GPU temperature, utilisation %, memory clock, and VRAM usage via pynvml.
    Gracefully no-ops if no NVIDIA GPU or driver is unavailable.
    """

    def __init__(self, max_temp: float, max_usage: float, max_vram_usage: float):
        super().__init__()
        self._max_temp = max_temp
        self._max_usage = max_usage
        self._max_vram_usage = max_vram_usage
        self._handle = None
        self._pynvml = None
        self._init_nvml()

    def _init_nvml(self) -> None:
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._pynvml = pynvml
        except Exception as e:
            get_logger().warning("pynvml unavailable — GPU metrics will not be monitored: %s", e)

    def read(self) -> list[MetricSnapshot]:
        if self._handle is None:
            return []

        snapshots = []
        try:
            temp = self._pynvml.nvmlDeviceGetTemperature(
                self._handle, self._pynvml.NVML_TEMPERATURE_GPU
            )
            snapshots.append(MetricSnapshot(
                label="GPU Temp",
                value=float(temp),
                unit="°C",
                threshold=self._max_temp,
            ))

            util = self._pynvml.nvmlDeviceGetUtilizationRates(self._handle)
            # Memory clock in MHz for the current utilisation state
            try:
                mem_clock_mhz = self._pynvml.nvmlDeviceGetClockInfo(
                    self._handle, self._pynvml.NVML_CLOCK_MEM
                )
                gpu_display = f"{util.gpu}% @ {mem_clock_mhz}MHz"
            except Exception:
                gpu_display = f"{util.gpu}%"

            snapshots.append(MetricSnapshot(
                label="GPU Usage",
                value=float(util.gpu),
                unit="%",
                threshold=self._max_usage,
                display_value=gpu_display,
            ))

            mem_info = self._pynvml.nvmlDeviceGetMemoryInfo(self._handle)
            vram_used_gb = round(mem_info.used / (1024 ** 3), 1)
            vram_total_gb = round(mem_info.total / (1024 ** 3), 1)
            vram_pct = round((mem_info.used / mem_info.total) * 100, 1)
            snapshots.append(MetricSnapshot(
                label="GPU VRAM",
                value=vram_pct,
                unit="%",
                threshold=self._max_vram_usage,
                display_value=f"{vram_used_gb} / {vram_total_gb}GB ({vram_pct}%)",
            ))
        except Exception as e:
            get_logger().warning("Failed to read GPU metrics: %s", e)

        return snapshots
