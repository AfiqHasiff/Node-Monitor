# Node Monitor

A lightweight Windows monitoring agent that runs silently in the background and sends system health alerts via Telegram.

## Features

- **CPU** — temperature (via LibreHardwareMonitor) and usage %
- **GPU** — temperature, usage %, and VRAM usage % (NVIDIA via pynvml)
- **RAM** — usage % (status reporting only)
- **Idle time** — time since last keyboard/mouse input
- Alerts fire **once** when a threshold is crossed, reset when the metric recovers — no spam
- On-demand `/status` command via Telegram
- Configurable thresholds in a single `config.yaml` — set any threshold to `0` to disable it
- Optional daily rotating log file
- Starts automatically at boot via Windows Task Scheduler

## Requirements

- Windows 10/11
- Python 3.11+
- NVIDIA GPU with drivers installed
- [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases) (for CPU temperature)

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up LibreHardwareMonitor

Download and run LHM as Administrator at least once so it registers its WMI provider. Enable **Run on Windows startup** and **Start minimized** in its Options menu.

> Without LHM, CPU temperature alerts are silently skipped — all other metrics still work.

### 3. Create a Telegram bot

1. Message **@BotFather** on Telegram → `/newbot`
2. Copy the **bot token** it gives you
3. Start a chat with your bot, then open:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   Find your **chat ID** in the response (`"chat":{"id": ...}`)

### 4. Configure

Edit `config.yaml`:

```yaml
telegram:
  bot_token: "123456789:AABBccDDeeFF..."
  chat_id: "123456789"

poll_interval_seconds: 30
logging_enabled: false   # set true to write logs to /logs/

idle:
  threshold_minutes: 240  # 0 = disabled

cpu:
  max_temp: 90            # 0 = disabled
  max_usage: 90

gpu:
  max_temp: 80
  max_usage: 95
  max_vram_usage: 90
```

### 5. Test manually

```bash
python main.py
```

Send `/status` to your Telegram bot — you should get a reply. Press `Ctrl+C` to stop.

### 6. Register with Task Scheduler

Edit the paths in `task_scheduler.xml` (replace `YOURUSERNAME` and the Python path), then import it via **Task Scheduler → Action → Import Task**.

See [SETUP.md](SETUP.md) for the full step-by-step guide.

## Project Structure

```
status-monitor/
├── main.py                   # Entry point
├── config.yaml               # Thresholds and credentials
├── requirements.txt
├── task_scheduler.xml        # Windows Task Scheduler import file
├── SETUP.md                  # Full setup guide
└── agent/
    ├── base_monitor.py       # Abstract base + shared alert state machine
    ├── config.py
    ├── logger.py
    ├── telegram_bot.py
    └── monitors/
        ├── cpu_monitor.py
        ├── gpu_monitor.py
        ├── ram_monitor.py
        └── idle_monitor.py
```

## Telegram Commands

| Command   | Description                          |
|-----------|--------------------------------------|
| `/status` | Current CPU, GPU, RAM, and idle time |

## Alert Example

```
🔥 CPU Temp Alert

Current: 92°C
Threshold: 90°C
```

Alerts only fire on the **rising edge** — no repeated notifications while the metric stays above threshold.
