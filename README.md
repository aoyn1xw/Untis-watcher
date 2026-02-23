# Untis Watcher

A simple Python-based Telegram bot that monitors WebUntis for timetable changes and sends notifications when updates are detected.

## Features

- Fetches timetable data from WebUntis
- Detects changes in lessons, rooms, or cancellations
- Sends automatic Telegram notifications
- Lightweight and easy to run locally or on a VPS

## Requirements

- Python 3.9+
- A WebUntis account
- A Telegram bot token

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

Create a `.env` file in the project root:

```
UNTIS_USERNAME=your_username
UNTIS_PASSWORD=your_password
UNTIS_SCHOOL=your_school_name
UNTIS_BASE_URL=https://your-school.webuntis.com
TELEGRAM_TOKEN=your_telegram_bot_token
CHAT_ID=your_telegram_chat_id
```

Replace all placeholder values with your actual credentials.

## Usage

Run the bot:

```bash
python main.py
```

The bot will periodically check for timetable changes and notify you via Telegram if any updates are found.

## Deployment Options

- Local machine (recommended)
- VPS with a German IP
- Cloud server (if not blocked by WebUntis)

## Disclaimer

This project uses WebUntis endpoints that are not officially documented. Functionality may break if WebUntis changes its internal API.

Use responsibly and ensure compliance with your school's policies.