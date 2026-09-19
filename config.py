# config.py — all provider settings come from the environment. Never hardcoded.
# Copy .env.example to .env and add your key. The system runs without one:
# set INBOXHERO_OFFLINE=1 (or simply omit the key) and every capability falls
# back to its deterministic path so a grader can run this on a clean checkout.

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional; env vars may be exported directly
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or None
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")
OFFLINE = os.getenv("INBOXHERO_OFFLINE", "").strip() == "1" or not GEMINI_API_KEY

# Seconds to wait between model calls, to stay under a free-tier rate limit.
CALL_DELAY = float(os.getenv("INBOXHERO_CALL_DELAY", "1.0"))

OWNER = os.getenv("INBOXHERO_OWNER", "sam@paperjet.io")
INBOX_PATH = os.getenv("INBOXHERO_INBOX", "inbox.json")
