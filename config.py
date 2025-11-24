# config.py

import os
import json # SERVICE_ACCOUNT_JSON ni tahlil qilish uchun
from dotenv import load_dotenv

load_dotenv()

# --- Telegram Sozlamalari ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Admin ID'larni vergul bilan ajratilgan satrdan butun sonlar ro'yxatiga aylantirish
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(',') if i.strip().isdigit()]

# --- NeonTech (PostgreSQL) Sozlamalari ---
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Google Sheets Sozlamalari (SERVICE_ACCOUNT_JSON orqali xavfsiz ulanish) ---
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
# JSON fayli kontentini Environment Variable dan o'qish (xavfsiz yechim)
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON") 

# --- Sheets Varaq Nomalari ---
SHEET_NAMES = {
    "AGENTS": "SAVDO AGENTLARI",         # Agentlar ro'yxatini yuritish uchun
    "PRODUCTS": "MAHSULOTLAR",           # Mahsulotlar ro'yxatini yuritish uchun
    "STOCK": "STOK_JAMI",                # Stok va qarzni umumiy kuzatish uchun
    "DEBT": "QARZDORLIK_JAMI",           # Qarz tranzaksiyalarini umumiy kuzatish uchun
    # SAVDO (SALES) varag'i dinamik bo'lgani uchun bu yerda yo'q
}

# --- Umumiy Sozlamalar ---
DEFAULT_UNIT = "kg"

# --- Webhook (Render.com) Sozlamalari ---
# Render avtomatik ravishda 'PORT' o'zgaruvchisini beradi
WEB_SERVER_HOST = '0.0.0.0' # Tashqi ulanishlar uchun
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# Domen nomini .env faylidan o'qiymiz (Render Web Service url manzili)
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = os.getenv("WEBHOOK_URL") + WEBHOOK_PATH
