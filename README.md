# Skipping Lecture

Automated PollEV answering bot with AI support and iMessage fallback.

## Quick Start

1. **Setup**: Download packages and configure API keys, classes, and contacts.
   ```bash
   python init.py
   ```

2. **Run**: Start the automation (handles login and monitoring).
   ```bash
   python run.py
   ```

   To run with helper/test mode (5s delay on iMessage listener):
   ```bash
   python run.py -test
   ```

## Detailed System Behavior

1. **Multi-Class Monitoring**:
   - The system checks your `classes.json` schedule.
   - It only launches browsers for classes that are currently "active" (within start/end time) or have no start time.
   - It creates a separate, isolated browser session for each class, spoofing the configured geolocation (Lat/Lon) to bypass attendance checks.

2. **AI Answering (Gemma)**:
   - When a poll question appears, the bot grabs the text and options.
   - It asks **Google Gemma 3 27b** for the best answer.
   - **High/Medium Confidence**: If Gemma is sure, the bot auto-clicks the answer immediately.
   - **Low Confidence/Error**: If the question is ambiguous (e.g., "What is the answer to the question on the board?"), Gemma flags it as "Low Confidence".

3. **Human-in-the-loop (iMessage Fallback)**:
   - If confidence is **Low**, the bot sends an **iMessage** to your configured recipient (e.g., a friend in class).
   - The message contains the Question and Numbered Options.
   - The bot waits for a reply (e.g., "3").
   - Once received, it clicks the corresponding option (Option 3).

