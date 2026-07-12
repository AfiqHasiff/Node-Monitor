# Node Monitor

A lightweight Windows monitoring agent that runs silently in the background, sends system health alerts via Telegram, and handles remote wake and shutdown commands via magic packets.

## Features

### Node Monitor
- **CPU** — temperature (via LibreHardwareMonitor) and usage % with real-time frequency
- **GPU** — temperature, usage % with memory clock, and VRAM usage with GB breakdown (NVIDIA)
- **RAM** — usage with GB breakdown (status reporting only)
- **Idle time** — time since last keyboard/mouse input, shown as `current / threshold`
- **Session** — logged-on Windows username and lock state
- Alerts fire **once** when a threshold is crossed, reset when the metric recovers — no spam
- When any threshold is breached, **one combined message** is sent showing all metrics with `⚠️` next to the offending ones
- On-demand `/status` command via Telegram — same layout as alerts
- Toggle on/off independently via `monitor.enabled` in `config.yaml`

### Packet Handler
- **Sender** — relays incoming WOL magic packets (subnet broadcast) and forwards shutdown commands to the target node
- **Receiver** — listens for shutdown signals; sends a Telegram alert when the node turns on or off, then executes system shutdown
- Sender and receiver are mutually exclusive per node — only one is enabled at a time via config
- Shutdown relay uses a custom sentinel signal (not raw magic packet bytes) to prevent accidentally waking the receiver NIC via WoL

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

Then set `monitor.lhm_dll_path` in `config.yaml` to the full path of `LibreHardwareMonitorLib.dll` inside that folder. The agent loads the DLL directly — no WMI provider required.

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

Edit `config.yaml`. The program is installed on both nodes but each node only enables the relevant features.

```yaml
telegram:
  bot_token: "123456789:AABBccDDeeFF..."
  chat_id:   "123456789"

packet_handler:
  sender:
    enabled:              false
    wake_listen_port:     8       # incoming WOL requests
    shutdown_listen_port: 9       # incoming shutdown requests
    target_ip:            "192.168.0.192"
    target_shutdown_port: 40002
    broadcast_ip:         "192.168.0.255"
    broadcast_port:       7       # WoL port on target NIC (typically 7 or 9)

  receiver:
    enabled:      false
    listen_port:  40002
    sender_ip:    "192.168.0.247"  # only accept signals from this IP
    node_ip:      "192.168.0.192"
    node_mac:     "aa:bb:cc:dd:ee:ff"

monitor:
  enabled:              true
  logging_enabled:      false     # set true to write logs to /logs/
  poll_interval_seconds: 30
  lhm_dll_path: "C:\\Tools\\LibreHardwareMonitor\\LibreHardwareMonitorLib.dll"
  idle:
    threshold_minutes: 60   # 0 = disabled
  cpu:
    max_temp:  90           # 0 = disabled
    max_usage: 0
  gpu:
    max_temp:      80
    max_usage:     0
    max_vram_usage: 0
```

**Sender node** — set `packet_handler.sender.enabled: true`, keep receiver and monitor flags as needed.

**Receiver node** — set `packet_handler.receiver.enabled: true`, keep sender and monitor flags as needed.

### 5. Test manually

```bash
python main.py
```

Send `/status` to your Telegram bot (when `monitor.enabled: true`). You should receive a reply like:

```
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
├── main.py                       # Entry point — starts monitor, sender, or receiver per config
├── config.yaml                   # All settings and credentials
├── requirements.txt
├── task_scheduler.xml            # Windows Task Scheduler import file
├── SETUP.md                      # Full setup guide
└── agent/
    ├── base_monitor.py           # Abstract base + shared alert state machine
    ├── config.py
    ├── logger.py                 # Unified logger — writes to /logs/ relative to project root
    ├── telegram_bot.py
    ├── packet_handler.py         # Sender and receiver thread logic
    └── monitors/
        ├── cpu_monitor.py        # Temp + usage % + frequency
        ├── gpu_monitor.py        # Temp + usage % + memory clock + VRAM
        ├── ram_monitor.py        # Usage with GB breakdown
        ├── idle_monitor.py       # Time since last input
        └── session_monitor.py    # Logged-on user + lock state
```

## Telegram Commands

| Command   | Description                                          |
|-----------|------------------------------------------------------|
| `/status` | Current readings for all metrics (monitor node only) |

## Alert Examples

### Threshold alert

When CPU temperature breaches its threshold, a single message is sent with all metrics:

```
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

### Node action alert

When the receiver node turns on or off, a Telegram alert is sent with the current metrics and an `Action` line:

```
⚡ Node Action

CPU Temp      54°C / 90°C
CPU Usage     12% @ 3.2GHz
GPU Temp      42°C / 80°C
GPU Usage     3% @ 7000MHz
GPU VRAM      1.1 / 16GB (7%)
RAM Usage     4.2 / 16GB (26%)
Idle Time     0m / 1h
Logged On     YourWindowsUsername
Action        Turned On
```

## Packet Handler — How It Works

```
[Someone]
    │  magic packet
    ▼
[Sender node — port 8 / 9]
    │
    ├─ wake:     rebroadcasts raw magic packet → 192.168.0.255:7 (NIC picks it up, powers on)
    │
    └─ shutdown: forwards SHUTDOWN sentinel → receiver node:40002 (application-level only,
                 NIC ignores it — no accidental WoL)

[Receiver node — port 40002]
    └─ validates sentinel + source IP → sends Turned Off alert → executes shutdown
```
