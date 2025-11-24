# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram Sozlamalari ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(',') if i.strip().isdigit()]

# --- NeonTech (PostgreSQL) Sozlamalari ---
DATABASE_URL = os.getenv("DATABASE_URL") # Neon Baza URLsi (.env faylida saqlanadi)

# --- Umumiy Sozlamalar ---
DEFAULT_UNIT = "kg"
