# Geser Flow ⏱

A lightweight Windows desktop app for tracking your work time — per project, with smart activity checks and break reminders.

> Stay in flow. Track what matters.

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
![Platform: Windows](https://img.shields.io/badge/Platform-Windows-lightgrey)

## What it does

- **Track work time per project** — start a session, pick a project, get a clean timer
- **Asks "Still working?"** every N minutes so you never forget to stop the timer
- **Auto-pauses** when you don't respond — no more inflated hours
- **Reminds you to take a break** after long focus sessions
- **Lives in your system tray** — always there, never in the way
- **Dashboard** with filtering by project, time period, and CSV export
- **Remembers your projects** with autocomplete from history
- **Detects unfinished sessions** on startup and lets you close them cleanly

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

## Run without console window (recommended)

Double-click `run.bat` or run:

```bash
pythonw main.py
```

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Check interval | 15 min | How often to ask "Still working?" |
| Check timeout | 60 sec | Time to respond before auto-pause |
| Break mode | On | Enable break reminders |
| Work interval | 90 min | Continuous work before break reminder |
| Break duration | 10 min | Suggested break length |
| Auto-start | Off | Launch with Windows |

All settings are configurable from the in-app settings window.

## Auto-start with Windows

Toggle it in the app's settings — it manages the Windows registry key automatically.

## Contributing

PRs are welcome. Open an issue for bugs or feature requests.

## License

MIT — Geser, 2025
