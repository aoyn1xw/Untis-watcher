# Untis Watcher

A Python-based Telegram bot that monitors WebUntis for timetable changes and sends AI-generated notifications when updates are detected.

## Features

- 📅 Fetches timetable data from WebUntis via JSON-RPC API
- 🔍 Detects changes in lessons, rooms, teachers, or cancellations
- 🤖 AI-powered summaries using GitHub Models (GPT-5)
- 📱 Automatic Telegram notifications
- 💾 Persistent storage to track changes across restarts
- 🔄 Continuous monitoring with configurable polling interval

## Requirements

- Python 3.9+
- A WebUntis account
- A Telegram bot token and your chat ID
- A GitHub personal access token (for GitHub Models AI)

## Installation

Clone the repository:

```bash
git clone https://github.com/aoyn1xw/Untis-watcher.git
cd Untis-watcher
```

Create and activate a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate  # macOS/Linux
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the instructions
3. Save the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
4. Start a chat with your new bot

### 2. Get Your Telegram Chat ID

1. Search for `@userinfobot` or `@get_id_bot` in Telegram
2. Start the bot and it will send you your chat ID
3. Save this ID (looks like `5131787452`)

### 3. Get GitHub Token for AI Models

1. Go to [GitHub Settings → Developer Settings → Personal Access Tokens](https://github.com/settings/tokens)
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a name like "Untis Watcher"
4. Select the `models:read` scope
5. Generate and save the token (looks like `github_pat_...`)

### 4. Find Your WebUntis Element ID

1. Log into WebUntis in your browser
2. Open Developer Tools (F12)
3. Go to the **Network** tab
4. Navigate to your timetable in WebUntis
5. Look for a request to `data` or `grid?timetableType=MY_TIMETABLE`
6. Check the Request URL or look in the JWT token for `person_id` or `elementId`
7. Save this number (e.g., `616`)

### 5. Create `.env` File

Create a `.env` file in the project root with the following content:

```env
# WebUntis Configuration
UNTIS_SERVER="your-school.webuntis.com"
UNTIS_SCHOOL="your-school-slug"
UNTIS_USER="your.username"
UNTIS_PASSWORD="your_password"
UNTIS_ELEMENT_TYPE="5"
UNTIS_ELEMENT_ID="your_element_id"

# GitHub Models (AI)
GITHUB_TOKEN="your_github_token"
AI_MODEL="gpt-5"

# Telegram
TELEGRAM_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_telegram_chat_id"

# Optional Settings
POLL_INTERVAL="300"
DAYS_AHEAD="7"
```

**Example with real values:**

```env
UNTIS_SERVER="ges-uellendahl-katernbe.webuntis.com"
UNTIS_SCHOOL="ges-uellendahl-katernbe"
UNTIS_USER="erdi.avdullahi"
UNTIS_PASSWORD="MyPassword123"
UNTIS_ELEMENT_TYPE="5"
UNTIS_ELEMENT_ID="616"

GITHUB_TOKEN="github_pat_11BPX6UBY0..."
AI_MODEL="gpt-5"

TELEGRAM_TOKEN="8539641488:AAHNTP9hFnL1oLnGbDLySV2GhagLHMaW8V0"
TELEGRAM_CHAT_ID="5131787452"

POLL_INTERVAL="300"
DAYS_AHEAD="7"
```

**Configuration Notes:**

- `UNTIS_SERVER`: Your WebUntis domain (from the URL)
- `UNTIS_SCHOOL`: The school slug (short name in the URL, not the full name)
- `UNTIS_ELEMENT_TYPE`: Usually `5` for student, `1` for class
- `UNTIS_ELEMENT_ID`: Your student/person ID from WebUntis
- `POLL_INTERVAL`: Seconds between checks (300 = 5 minutes)
- `DAYS_AHEAD`: How many days of timetable to fetch

## Usage

Run the bot:

```bash
python main.py
```

On startup, you'll receive a Telegram message confirming the bot is running. The bot will:

1. Fetch your current timetable from WebUntis
2. Check for changes every 5 minutes (configurable)
3. Send AI-generated summaries of any changes to Telegram
4. Continuously monitor until stopped with `Ctrl+C`

**First run:** The bot will save your current timetable as a baseline and won't send notifications until actual changes are detected.

## Deployment Options

### Local Machine (Recommended for Testing)
- Keep the script running in a terminal
- Use `Ctrl+C` to stop

### Windows (Background Service)
- Use Task Scheduler to run at startup
- Or use `pythonw main.py` to run without console

### VPS/Cloud Server
- Use `screen` or `tmux` to keep it running:
  ```bash
  screen -S untis-watcher
  python main.py
  # Press Ctrl+A, then D to detach
  ```
- Or create a systemd service (Linux)

### Docker (Optional)
- Can be containerized for easier deployment
- Useful for running on cloud platforms

## Troubleshooting

### 403 Forbidden Error
- Check that `UNTIS_SCHOOL` is the short slug (e.g., `school-name`), not the full name
- Verify your `UNTIS_ELEMENT_ID` is correct
- Make sure your WebUntis credentials are valid

### Bot Can't Send Messages
- Ensure `TELEGRAM_CHAT_ID` is your personal ID, not the bot's ID
- Make sure you've started a chat with your bot first

### AI Model Errors
- Verify your GitHub token has `models:read` permissions
- Check that `AI_MODEL` is set to `gpt-5` or another valid model
- Ensure you're within GitHub Models rate limits

### No Changes Detected
- The bot only notifies on changes, not on every poll
- Check that `POLL_INTERVAL` isn't too long
- Verify the timetable data is being fetched correctly

## Project Structure

```
Untis-watcher/
├── main.py          # Entry point and polling loop
├── timetable.py     # WebUntis API integration (JSON-RPC)
├── detector.py      # Change detection logic
├── ai.py           # GitHub Models integration
├── notifier.py      # Telegram notifications
├── storage.py       # Persistent timetable storage
├── config.py        # Environment variable loading
├── requirements.txt # Python dependencies
└── .env            # Configuration (not in git)
```

## How It Works

1. **Authentication**: Logs into WebUntis using JSON-RPC API
2. **Fetching**: Retrieves the weekly timetable for your student ID
3. **Change Detection**: Compares with previous timetable to find differences
4. **AI Analysis**: GitHub Models (GPT-5) generates a friendly summary
5. **Notification**: Sends the summary to your Telegram
6. **Storage**: Saves the current timetable for next comparison

## Change Types Detected

- 🔺 **Cancellations** (Entfall): Free periods
- 🟢 **Changes** (Änderung): Room, teacher, or time modifications  
- 🟡 **Exams** (Prüfung): Detected by keywords in subject names
- ➕ **Additions**: New lessons added to timetable
- ➖ **Removals**: Lessons removed from timetable

## Disclaimer

This project uses WebUntis JSON-RPC API endpoints that are not officially documented. Functionality may break if WebUntis changes its internal API.

**Important:**
- Use responsibly and ensure compliance with your school's policies
- Keep your credentials secure (never commit `.env` to git)
- Be mindful of API rate limits
- This is for personal use only

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## License

See [LICENSE](LICENSE) file for details.

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review your `.env` configuration
3. Open an issue on GitHub with error details