# Untis Watcher - Executable Guide

## Quick Start

Your Untis Watcher is now available as a standalone executable at:
`dist\UntisWatcher.exe`

### To Run:
1. **Double-click** `UntisWatcher.exe`
2. The program will start **silently** in your system tray (no console window)
3. Look for the **blue circle icon** in your system tray (bottom-right of taskbar)
4. **Right-click** the icon to quit the application

## Features

✅ Runs completely in the background (no console window)
✅ Lives in the system tray with an icon
✅ Monitors your WebUntis timetable for changes
✅ Sends Telegram notifications when changes are detected
✅ Starts with a confirmation notification

## Auto-Start on Windows Boot

To make Untis Watcher start automatically when Windows boots:

### Method 1: Startup Folder (Recommended)
1. Press `Win + R` to open Run dialog
2. Type `shell:startup` and press Enter
3. Copy or create a shortcut to `UntisWatcher.exe` into this folder

### Method 2: Task Scheduler (Advanced)
1. Open Task Scheduler (`taskschd.msc`)
2. Create a new task
3. Set trigger to "At log on"
4. Set action to run `UntisWatcher.exe`
5. Configure to run with highest privileges

## Configuration

Before running the executable, ensure your `.env` file is in the **same directory** as `UntisWatcher.exe`.

Required `.env` variables:
```
UNTIS_SCHOOL=your_school
UNTIS_USERNAME=your_username
UNTIS_PASSWORD=your_password
UNTIS_SERVER=your_server
UNTIS_USERAGENT=your_useragent

OPENAI_KEY=your_openai_api_key

TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

POLL_INTERVAL=300
```

## Rebuilding the Executable

If you make changes to the Python code and want to rebuild:

### Option 1: Double-click
Simply double-click `build.bat`

### Option 2: Command Line
```powershell
python build_exe.py
```

### Option 3: Using PyInstaller directly
```powershell
pyinstaller UntisWatcher.spec
```

## Troubleshooting

### Icon doesn't appear in system tray
- Check Task Manager to see if the process is running
- Make sure `.env` file is in the same directory as the exe
- Check that all required environment variables are set

### "Missing .env file" error
- The `.env` file must be in the **same directory** as `UntisWatcher.exe`
- If you move the exe, move the `.env` file with it

### Changes not detected
- Check your WebUntis credentials in `.env`
- Check your internet connection
- The polling interval is set in `.env` (default 300 seconds)

### No Telegram messages
- Verify your Telegram bot token and chat ID in `.env`
- Test your bot by sending a message to it first

## Technical Details

- **Build Tool**: PyInstaller 6.19.0
- **Python Version**: 3.13.11
- **Architecture**: Windows 64-bit
- **Mode**: Windowed (no console), Single-file executable
- **Libraries**: PIL, pystray, requests, openai, python-telegram-bot

## File Structure

```
Untis-watcher/
├── dist/
│   └── UntisWatcher.exe    ← Your executable
├── build/                   ← Build artifacts (can be deleted)
├── main.py                  ← Source code
├── build_exe.py            ← Build script
├── UntisWatcher.spec       ← PyInstaller configuration
├── build.bat               ← Quick build batch file
├── .env                    ← Configuration (keep with exe!)
└── requirements.txt        ← Python dependencies
```

## Distributing

To share the executable with others:
1. Copy `dist\UntisWatcher.exe`
2. Include a template `.env` file
3. Share this guide

**Note**: Each user needs their own `.env` with their credentials.

## Uninstalling

Simply:
1. Right-click the system tray icon and quit
2. Delete `UntisWatcher.exe`
3. Remove from startup folder if you added it there

---

**Happy timetable watching!** 📚⏰
