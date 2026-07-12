"""
PC Monitoring Agent — entry point.

Starts the async polling loop and Telegram bot together.
All monitors are polled every `poll_interval_seconds`.
Alerts fire on the rising edge only (threshold crossed from below).
When any metric breaches its threshold, one combined message is sent with all metrics.

Each feature segment is independently toggled via config.yaml:
  node_monitor.enabled  — periodic polling alerts and /status command
  packet_handler.sender.enabled   — WOL / shutdown relay threads
  packet_handler.receiver.enabled — shutdown listener + Turned On/Off alerts
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
from agent.packet_handler import start_sender, start_receiver


async def main() -> None:
    try:
        cfg = load_config()
    except Exception as e:
        print(f"ERROR: Failed to load config.yaml — {e}", file=sys.stderr)
        sys.exit(1)

    monitor_cfg: dict = cfg.get("monitor", {})
    logger = setup_logger(monitor_cfg.get("logging_enabled", False))
    logger.info("Agent started")

    node_monitor_enabled: bool = monitor_cfg.get("enabled", True)
    ph_cfg: dict = cfg.get("packet_handler", {})
    sender_cfg: dict = ph_cfg.get("sender", {})
    receiver_cfg: dict = ph_cfg.get("receiver", {})
    sender_enabled: bool = sender_cfg.get("enabled", False)
    receiver_enabled: bool = receiver_cfg.get("enabled", False)

    # Warm up psutil cpu_percent — first call always returns 0.0
    psutil.cpu_percent(interval=None)

    cpu = CpuMonitor(
        max_temp=monitor_cfg["cpu"]["max_temp"],
        max_usage=monitor_cfg["cpu"]["max_usage"],
        dll_path=monitor_cfg.get("lhm_dll_path", ""),
    )
    gpu = GpuMonitor(
        max_temp=monitor_cfg["gpu"]["max_temp"],
        max_usage=monitor_cfg["gpu"]["max_usage"],
        max_vram_usage=monitor_cfg["gpu"]["max_vram_usage"],
    )
    ram = RamMonitor()
    idle = IdleMonitor(threshold_minutes=monitor_cfg["idle"]["threshold_minutes"])
    session = SessionMonitor()

    monitors = [cpu, gpu, ram, idle, session]
    poll_interval = monitor_cfg.get("poll_interval_seconds", 30)

    async def get_status() -> list[MetricSnapshot]:
        snapshots = []
        for monitor in monitors:
            snapshots.extend(monitor.read())
        return snapshots

    bot = TelegramBot(
        bot_token=cfg["telegram"]["bot_token"],
        chat_id=str(cfg["telegram"]["chat_id"]),
        status_callback=get_status,
        node_monitor_enabled=node_monitor_enabled,
    )

    await bot.start()

    loop = asyncio.get_running_loop()

    if sender_enabled:
        start_sender(sender_cfg)
        logger.info("Packet sender started")

    if receiver_enabled:
        async def _action_alert(action: str) -> None:
            snapshots = await get_status()
            await bot.send_action_alert(action, snapshots)

        start_receiver(receiver_cfg, loop, _action_alert)
        logger.info("Packet receiver started")

    stop_event = asyncio.Event()

    def _shutdown(*_):
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Monitoring started — poll interval %ds", poll_interval)

    while not stop_event.is_set():
        await asyncio.sleep(poll_interval)

        if not node_monitor_enabled:
            continue

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
