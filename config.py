# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
CONTEST_DURATION = int(os.getenv("CONTEST_DURATION", "300"))
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "5"))