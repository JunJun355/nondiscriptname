# PollEV Auto-Attendant

Automatically attend PollEV sessions with AI-powered question answering.

## Setup

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install playwright google-generativeai beautifulsoup4 lxml
playwright install chromium
```

### 2. Add Your API Key
Create a file `data/API_KEY_GEMINI` containing your Google Gemini API key:
```bash
echo "your-api-key-here" > data/API_KEY_GEMINI
```

### 3. Configure Your Classes
Edit `data/classes.json` with your class details:
```json
[
  {
    "name": "CS_101",
    "section": "professor id",
    "longitude": -76.4735,
    "latitude": 42.4534,
    "start_time": "10:00:00",
    "end_time": "11:00:00"
  }
]
```
- `section`: The presenter's PollEV username (from pollev.com/**section**)
- `longitude/latitude`: GPS coordinates to spoof (for geofenced polls)
- `start_time/end_time`: When to automatically join (leave empty to join immediately)

### 4. Login Manually
```bash
python src/login.py
```
Log in manually in the browser, then press Enter in the terminal to save your login session token.

---

## Usage

### Run the Monitor
```bash
python src/monitor.py
```

The monitor will:
1. ⏰ Wait until class `start_time`
2. 🌐 Open PollEV with spoofed GPS location
3. 👁️ Watch for new poll questions
4. 🤖 Ask Gemma AI for the best answer
5. 🖱️ Click the answer automatically
6. 🔔 Send a Mac notification if confidence is low

### Stop the Monitor
Press **Enter** in the terminal for a graceful shutdown.

---

## Notifications

| Confidence | Behavior |
|------------|----------|
| 🟢 High | Clicks silently |
| 🟡 Medium | Clicks silently |
| 🔴 Low | Clicks + Mac notification |
| ❌ Error | Notification only |

To make notifications **persist until dismissed**:
- System Settings → Notifications → Terminal → Change to "Alerts"
