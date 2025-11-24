# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# --- Telegram Sozlamalari ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(',') if i.strip().isdigit()]

# --- NeonTech (PostgreSQL) Sozlamalari ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Google Sheets Sozlamalari (Yangi) ---
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SERVICE_ACCOUNT_FILE = 'service_account.json' # Sheetsga ulanish uchun JSON fayl nomi

# --- Sheets Varaq Nomalari (Faqat baza va agentlar uchun, chunki savdo dinamik) ---
SHEET_NAMES = {
    "AGENTS": "SAVDO AGENTLARI",         # Agentlar ro'yxatini yuritish uchun
    "PRODUCTS": "MAHSULOTLAR",           # Mahsulotlar ro'yxatini yuritish uchun
    "STOCK": "STOK_JAMI",                # Stok va qarzni umumiy kuzatish uchun
    "DEBT": "QARZDORLIK_JAMI",           # Qarz tranzaksiyalarini umumiy kuzatish uchun
    # SAVDO (SALES) varag'i endi dinamik nomlanadi: YYYY-MM
}

# --- Umumiy Sozlamalar ---
DEFAULT_UNIT = "kg"
