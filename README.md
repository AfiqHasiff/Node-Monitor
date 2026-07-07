# Node Monitor

A lightweight Windows monitoring agent that runs silently in the background and sends system health alerts via Telegram.

## Features

- **CPU** — temperature (via LibreHardwareMonitor) and usage % with real-time frequency
- **GPU** — temperature, usage % with memory clock, and VRAM usage with GB breakdown (NVIDIA)
- **RAM** — usage with GB breakdown (status reporting only)
- **Idle time** — time since last keyboard/mouse input, shown as `current / threshold`
- **Session** — logged-on Windows username and lock state
- Alerts fire **once** when a threshold is crossed, reset when the metric recovers — no spam
- When any threshold is breached, **one combined message** is sent showing all metrics with `⚠️` next to the offending ones
- On-demand `/status` command via Telegram — same layout as alerts
- Configurable thresholds in `config.yaml` — set any threshold to `0` to disable it
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

Download and extract to a permanent folder (e.g. `C:\Tools\LibreHardwareMonitor\`), run as Administrator, and enable **Run on Windows startup** + **Start minimized** in Options.

Then set `lhm_dll_path` in `config.yaml` to the full path of `LibreHardwareMonitorLib.dll` inside that folder. The agent loads the DLL directly — no WMI provider required.

> Without LHM the agent still runs — CPU temperature is skipped and retried each poll cycle until the DLL becomes accessible.

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

lhm_dll_path: "C:\\Tools\\LibreHardwareMonitor\\LibreHardwareMonitorLib.dll"

poll_interval_seconds: 30
logging_enabled: false   # set true to write logs to /logs/

idle:
  threshold_minutes: 60   # 0 = disabled

cpu:
  max_temp: 90            # 0 = disabled
  max_usage: 0            # 0 = disabled

gpu:
  max_temp: 80
  max_usage: 0            # 0 = disabled
  max_vram_usage: 0       # 0 = disabled
```

### 5. Test manually

```bash
python main.py
```

Send `/status` to your Telegram bot. You should receive a reply like:

```text
🖥 Node Status

CPU Temp      54°C / 90°C
CPU Usage     34% @ 3.8GHz
GPU Temp      47°C / 80°C
GPU Usage     12% @ 7000MHz
GPU VRAM      6.2 / 16GB (41%)
RAM Usage     6.3 / 16GB (39%)
Idle Time     2m / 1h
Logged On     YourWindowsUsername
```

Press `Ctrl+C` to stop.

### 6. Register with Task Scheduler

Edit the paths in `task_scheduler.xml` (replace `YOURUSERNAME` and the Python path), then import it via **Task Scheduler → Action → Import Task**.

See [SETUP.md](SETUP.md) for the full step-by-step guide.

## Project Structure

```text
status-monitor/
├── main.py                       # Entry point
├── config.yaml                   # Thresholds and credentials
├── requirements.txt
├── task_scheduler.xml            # Windows Task Scheduler import file
├── SETUP.md                      # Full setup guide
└── agent/
    ├── base_monitor.py           # Abstract base + shared alert state machine
    ├── config.py
    ├── logger.py
    ├── telegram_bot.py
    └── monitors/
        ├── cpu_monitor.py        # Temp + usage % + frequency
        ├── gpu_monitor.py        # Temp + usage % + memory clock + VRAM
        ├── ram_monitor.py        # Usage with GB breakdown
        ├── idle_monitor.py       # Time since last input
        └── session_monitor.py    # Logged-on user + lock state
```

## Telegram Commands

| Command   | Description                      |
|-----------|----------------------------------|
| `/status` | Current readings for all metrics |

## Alert Example

When CPU temperature breaches its threshold, a single message is sent with all metrics:

```text
⚠️ Threshold Alert

CPU Temp      92°C / 90°C  ⚠️
CPU Usage     34% @ 3.8GHz
GPU Temp      47°C / 80°C
GPU Usage     12% @ 7000MHz
GPU VRAM      6.2 / 16GB (41%)
RAM Usage     6.3 / 16GB (39%)
Idle Time     2m / 1h
Logged On     YourWindowsUsername
```

Alerts only fire on the **rising edge** — no repeated notifications while the metric stays above threshold. Once it drops back below, the alert resets and will fire again if it breaches again.
