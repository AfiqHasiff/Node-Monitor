# Setup Guide

## Prerequisites

- Windows 10/11
- Python 3.11+ installed and on PATH
- NVIDIA GPU with drivers installed

---

## Step 1 — Install Python dependencies

Open a terminal in the project folder and run:

```
pip install -r requirements.txt
```

---

## Step 2 — Install LibreHardwareMonitor (for CPU temperature)

CPU temperature on Windows is not exposed via standard APIs. We use
LibreHardwareMonitor as a WMI bridge.

1. Download the latest release from:
   https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases

2. Extract the zip to a permanent location (e.g. `C:\Tools\LibreHardwareMonitor\`)

3. Extract the zip to a permanent location, e.g.:
   ```
   C:\Tools\LibreHardwareMonitor\
   ```

4. Run `LibreHardwareMonitor.exe` as Administrator. In the Options menu enable:
   - **Run on Windows startup**
   - **Start minimized**

5. Note the path to `LibreHardwareMonitorLib.dll` inside that folder — you will need
   it in Step 4.

> The agent loads the LHM DLL directly via pythonnet — no WMI provider is needed.
> If the DLL path is wrong or LHM is missing, CPU temperature is skipped and retried
> each poll cycle. All other metrics continue working.

---

## Step 3 — Create a Telegram bot

1. Open Telegram and search for **@BotFather**.

2. Send the command `/newbot` and follow the prompts:
   - Choose a name (e.g. `My PC Monitor`)
   - Choose a username ending in `bot` (e.g. `mypc_monitor_bot`)

3. BotFather will reply with a **bot token** like:
   ```
   123456789:AABBccDDeeFFggHHiiJJkkLLmmNNooPPqq
   ```
   Copy this token.

4. Start a chat with your new bot (search for it by username and press Start).

5. Get your **chat ID**:
   - Send any message to your bot.
   - Open this URL in a browser (replace `<TOKEN>` with your token):
     ```
     https://api.telegram.org/bot<TOKEN>/getUpdates
     ```
   - Find `"chat":{"id": 123456789 ...}` in the response. That number is your chat ID.

---

## Step 4 — Configure the agent

Edit `config.yaml` and fill in your token, chat ID, and LHM DLL path:

```yaml
telegram:
  bot_token: "123456789:AABBccDDeeFFggHHiiJJkkLLmmNNooPPqq"
  chat_id: "123456789"

lhm_dll_path: "C:\\Tools\\LibreHardwareMonitor\\LibreHardwareMonitorLib.dll"
```

Adjust thresholds to suit your hardware. Set any threshold to `0` to disable that alert:

```yaml
poll_interval_seconds: 30

logging_enabled: false   # set to true to write daily log files to /logs/

idle:
  threshold_minutes: 60   # alert after 1 hour idle; 0 = disabled

cpu:
  max_temp: 90             # 0 = disabled
  max_usage: 0             # 0 = disabled

gpu:
  max_temp: 80             # 0 = disabled
  max_usage: 0             # 0 = disabled
  max_vram_usage: 0        # 0 = disabled
```

---

## Step 5 — Test manually

Run the agent from the terminal to verify everything works before scheduling:

```
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

Press Ctrl+C to stop.

---

## Step 6 — Register with Windows Task Scheduler

This makes the agent start automatically on Windows boot and restart if it crashes.

### Option A — Import the provided XML (easiest)

1. Open `task_scheduler.xml` in a text editor and replace all occurrences of
   `YOURUSERNAME` with your Windows username, and update the Python path if needed.

2. Open **Task Scheduler** (search in Start menu).

3. Click **Action → Import Task...** and select `task_scheduler.xml`.

4. Click **OK**. You may be asked to enter your Windows password.

### Option B — Create the task manually

1. Open **Task Scheduler** → **Create Task...**

2. **General tab:**
   - Name: `PC Monitor Agent`
   - Check **Run whether user is logged on or not**
   - Check **Run with highest privileges**

3. **Triggers tab → New:**
   - Begin the task: **At startup**
   - Delay task for: `30 seconds`

4. **Actions tab → New:**
   - Action: **Start a program**
   - Program/script: full path to `pythonw.exe`
     (e.g. `C:\Users\YourName\AppData\Local\Programs\Python\Python311\pythonw.exe`)
   - Add arguments: `main.py`
   - Start in: full path to the project folder
     (e.g. `C:\Users\YourName\Documents\ResearchProject\status-monitor`)

5. **Settings tab:**
   - Check **If the task fails, restart every:** `1 minute`, up to `3 times`
   - Uncheck **Stop the task if it runs longer than**

6. Click **OK** and enter your Windows password when prompted.

> Use `pythonw.exe` (not `python.exe`) so no console window appears.

---

## Enabling logs

To turn on diagnostic logging, open `config.yaml` and set:

```yaml
logging_enabled: true
```

Log files are written to the `logs/` folder as `monitor_agent.log`, rotating at
midnight and keeping the last 30 days. Set it back to `false` when no longer needed.

---

## Available Telegram commands

| Command   | Description                      |
|-----------|----------------------------------|
| `/status` | Current readings for all metrics |

---

## Metrics reference

| Metric       | Source                         | Alert support | Example display         |
|--------------|--------------------------------|---------------|-------------------------|
| CPU Temp     | LibreHardwareMonitor (WMI)     | Yes           | `92°C`                  |
| CPU Usage    | psutil                         | Yes           | `34% @ 3.8GHz`          |
| GPU Temp     | pynvml (NVIDIA)                | Yes           | `47°C`                  |
| GPU Usage    | pynvml (NVIDIA)                | Yes           | `12% @ 7000MHz`         |
| GPU VRAM     | pynvml (NVIDIA)                | Yes           | `6.2 / 16GB (41%)`      |
| RAM Usage    | psutil                         | No            | `6.3 / 16GB (39%)`      |
| Idle Time    | Win32 GetLastInputInfo         | Yes           | `2m / 1h`               |
| Logged On    | Win32 WTS session API          | No            | `User (Locked)`         |
