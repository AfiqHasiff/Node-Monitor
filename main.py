"""
PC Monitoring Agent — entry point.

Starts the async polling loop and Telegram bot together.
All monitors are polled every `poll_interval_seconds`.
Alerts fire on the rising edge only (threshold crossed from below).
When any metric breaches its threshold, one combined message is sent with all metrics.
"""

import asyncio
import signal
import sys

import psutil

from agent.config import load_config
from agent.logger import setup_logger, get_logger
from agent.base_monitor import MetricSnapshot
from agent.monitors.cpu_monitor import CpuMonitor
from agent.monitors.gpu_monitor import GpuMonitor
from agent.monitors.ram_monitor import RamMonitor
from agent.monitors.idle_monitor import IdleMonitor
from agent.monitors.session_monitor import SessionMonitor
from agent.telegram_bot import TelegramBot


async def main() -> None:
    try:
        cfg = load_config()
    except Exception as e:
        print(f"ERROR: Failed to load config.yaml — {e}", file=sys.stderr)
        sys.exit(1)

    logger = setup_logger(cfg.get("logging_enabled", False))
    logger.info("Agent started")

    # Warm up psutil cpu_percent — first call always returns 0.0
    psutil.cpu_percent(interval=None)

    cpu = CpuMonitor(
        max_temp=cfg["cpu"]["max_temp"],
        max_usage=cfg["cpu"]["max_usage"],
    )
    gpu = GpuMonitor(
        max_temp=cfg["gpu"]["max_temp"],
        max_usage=cfg["gpu"]["max_usage"],
        max_vram_usage=cfg["gpu"]["max_vram_usage"],
    )
    ram = RamMonitor()
    idle = IdleMonitor(threshold_minutes=cfg["idle"]["threshold_minutes"])
    session = SessionMonitor()

    monitors = [cpu, gpu, ram, idle, session]
    poll_interval = cfg.get("poll_interval_seconds", 30)

    async def get_status() -> list[MetricSnapshot]:
        snapshots = []
        for monitor in monitors:
            snapshots.extend(monitor.read())
        return snapshots

    bot = TelegramBot(
        bot_token=cfg["telegram"]["bot_token"],
        chat_id=str(cfg["telegram"]["chat_id"]),
        status_callback=get_status,
    )

    await bot.start()

    stop_event = asyncio.Event()

    def _shutdown(*_):
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Monitoring started — poll interval %ds", poll_interval)

    while not stop_event.is_set():
        await asyncio.sleep(poll_interval)

        all_snapshots: list[MetricSnapshot] = []
        newly_triggered: list[str] = []

        for monitor in monitors:
            snapshots = monitor.read()
            all_snapshots.extend(snapshots)

            alerts = monitor.check_alerts(snapshots)
            for alert in alerts:
                newly_triggered.append(f"{alert.label} {alert.value}{alert.unit}")

        if newly_triggered:
            for label_str in newly_triggered:
                logger.info("%s alert sent", label_str)
            await bot.send_alert(all_snapshots)

        for s in all_snapshots:
            logger.info("%s %s%s", s.label, s.value, s.unit)

    logger.info("Agent stopping")
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
