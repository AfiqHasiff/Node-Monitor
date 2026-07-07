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

3. Run `LibreHardwareMonitor.exe` **as Administrator** at least once so it
   installs the WMI provider.

4. In the Options menu, enable:
   - **Run on Windows startup**
   - **Start minimized**

   This ensures the WMI bridge is available before the monitoring agent polls.

> If LHM is not running, the agent will still work — CPU temperature will simply
> be absent from readings and alerts. All other metrics continue normally.

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

Edit `config.yaml` and fill in your token and chat ID:

```yaml
telegram:
  bot_token: "123456789:AABBccDDeeFFggHHiiJJkkLLmmNNooPPqq"
  chat_id: "123456789"
```

Adjust thresholds to suit your hardware:

```yaml
poll_interval_seconds: 30

logging_enabled: false   # set to true to write daily log files to /logs/

idle:
  threshold_minutes: 240

cpu:
  max_temp: 90
  max_usage: 90

gpu:
  max_temp: 80
  max_usage: 95
  max_vram_usage: 90
```

---

## Step 5 — Test manually

Run the agent from the terminal to verify everything works before scheduling:

```
python main.py
```

Send `/status` to your Telegram bot. You should receive a status reply.
Press Ctrl+C to stop.

---

## Step 6 — Register with Windows Task Scheduler

This makes the agent start automatically on Windows boot and restart if it crashes.

### Option A — Import the provided XML (easiest)

1. Open **Task Scheduler** (search in Start menu).
2. Click **Action → Import Task...**.
3. Select `task_scheduler.xml` from the project folder.
4. In the **General** tab, change the user account to your own Windows username.
5. Click **OK**. You may be asked to enter your Windows password.

### Option B — Create the task manually

1. Open **Task Scheduler** → **Create Task...**

2. **General tab:**
   - Name: `PC Monitor Agent`
   - Check **Run whether user is logged on or not**
   - Check **Run with highest privileges**

3. **Triggers tab → New:**
   - Begin the task: **At startup**
   - Delay task for: `30 seconds` (gives Windows time to fully boot)

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

Log files are written to the `logs/` folder, named by date (e.g. `2026-07-07.log`).
Set it back to `false` when you no longer need them.

---

## Available Telegram commands

| Command   | Description                                  |
|-----------|----------------------------------------------|
| `/status` | Returns current CPU, GPU, RAM, and idle time |
