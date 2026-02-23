# 🚀 Quick Start - Untis Watcher System Tray App

## ✅ What's Ready

Your Untis Watcher is now a Windows executable that runs in the system tray!

**Location**: `dist\UntisWatcher.exe`

## 🎯 How to Use

### First Time Setup
1. Navigate to the `dist` folder
2. Make sure `.env` file is there (it was automatically copied)
3. Double-click `UntisWatcher.exe`
4. Look for the **blue circle icon** in your system tray (bottom-right)
5. You'll get a Telegram notification that it's running

### To Stop
- Right-click the tray icon → select "Quit"

### To Run on Startup
**Quick Method:**
1. Press `Win + R`
2. Type `shell:startup` and press Enter
3. Copy `UntisWatcher.exe` and `.env` to this folder
   - OR create a shortcut to the exe

## 📁 Files You Need

```
dist/
├── UntisWatcher.exe    ← The executable
└── .env                ← Your configuration (MUST be in same folder)
```

## ⚙️ Configuration (.env file)

Make sure your `.env` file contains:
```env
UNTIS_SERVER=your_server
UNTIS_SCHOOL=your_school
UNTIS_USER=your_username
UNTIS_PASSWORD=your_password
UNTIS_ELEMENT_TYPE=5
UNTIS_ELEMENT_ID=your_id

GITHUB_TOKEN=your_github_token
AI_MODEL=gpt-4o-mini

TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

POLL_INTERVAL=300
DAYS_AHEAD=7
```

## 🔄 Rebuilding (After Code Changes)

If you modify the Python code:

**Option 1:** Double-click `build.bat`  
**Option 2:** Run `python build_exe.py`

The new exe will be in the `dist` folder.

## 🎉 That's It!

Your timetable watcher now:
- ✅ Runs silently in the system tray
- ✅ No console window
- ✅ Can auto-start with Windows
- ✅ Shows a tray icon you can right-click to quit
- ✅ Sends Telegram notifications for timetable changes

## 📖 More Details

See `EXECUTABLE_GUIDE.md` for comprehensive documentation.

---

**Enjoy your automated timetable watching!** 📚
