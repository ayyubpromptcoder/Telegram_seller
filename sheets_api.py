import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime
import json
from config import SPREADSHEET_ID, SHEET_NAMES, SERVICE_ACCOUNT_JSON

# Asyncio bilan sinxron kodni bloklanmasdan ishlatish uchun
import asyncio

logging.basicConfig(level=logging.INFO)

# ==============================================================================
# I. GOOGLE SHEETSGA ULANISH FUNKSIYASI (SINXRON - o'zgarmadi)
# ==============================================================================

def get_sheets_client():
    """Google Sheetsga ulanishni ta'minlaydi (SERVICE_ACCOUNT_JSON orqali)."""
    try:
        if not SPREADSHEET_ID or not SERVICE_ACCOUNT_JSON:
            logging.error("SPREADSHEET_ID yoki SERVICE_ACCOUNT_JSON o'rnatilmagan.")
            return None
            
        creds_json = json.loads(SERVICE_ACCOUNT_JSON)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_json, scopes=scope) 
        
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return spreadsheet
    except Exception as e:
        logging.error(f"Google Sheetsga ulanishda xato: {e}")
        return None

# ==============================================================================
# II. YORDAMCHI FUNKSIYALAR (SINXRON - o'zgarmadi)
# ==============================================================================

def get_or_create_monthly_sheet(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    """Joriy oy uchun (YYYY-MM) varaqni topadi yoki yaratadi."""
    now = datetime.now()
    month_name = now.strftime("%Y-%m")
    
    try:
        worksheet = spreadsheet.worksheet(month_name)
        logging.info(f"Varaq topildi: {month_name}")
        return worksheet
    except gspread.WorksheetNotFound:
        logging.info(f"Varaq topilmadi, {month_name} yaratilmoqda...")
        worksheet = spreadsheet.add_worksheet(title=month_name, rows=1000, cols=15)
        header = [
            "Sana (YYYY-MM-DD)", "Vaqt (HH:MM:SS)", "Agent_Ismi", "Mahsulot_Nomi", 
            "Miqdor_KG", "Savdo_Narxi", "Jami_Summa"
        ]
        worksheet.append_row(header)
        logging.info(f"Yangi varaq {month_name} muvaffaqiyatli yaratildi.")
        return worksheet
    except Exception as e:
        logging.error(f"Oylik varaq bilan ishlashda xato: {e}")
        return None

# ==============================================================================
# III. MA'LUMOT KIRITISH (SINXRON) FUNKSIYALARI - o'zgarmadi
# ==============================================================================

def write_stock_txn_to_sheets_sync(agent_name: str, product_name: str, qty_kg: float, issue_price: float, total_cost: float) -> bool:
    """Agentga berilgan tovar (stok) amaliyotini Sheetsga yozadi."""
    spreadsheet = get_sheets_client()
    if not spreadsheet: return False

    try:
        worksheet = spreadsheet.worksheet(SHEET_NAMES["STOCK"])
        now = datetime.now()
        row = [
            now.strftime("%Y-%m-%d %H:%M:%S"),
            agent_name,
            product_name,
            qty_kg,
            issue_price,
            total_cost
        ]
        worksheet.append_row(row)
        return True
    except Exception as e:
        logging.error(f"Stok tranzaksiyasini Sheetsga yozishda xato: {e}")
        return False

def write_debt_txn_to_sheets_sync(agent_name: str, txn_type: str, amount: float, txn_date: str, comment: str) -> bool:
    """Agentning pul to'lovi yoki avans amaliyotini Sheetsga yozadi."""
    spreadsheet = get_sheets_client()
    if not spreadsheet: return False

    try:
        worksheet = spreadsheet.worksheet(SHEET_NAMES["DEBT"])
        row = [
            txn_date,
            agent_name,
            txn_type,
            amount, # Manfiy yoki Musbat qiymat
            comment
        ]
        worksheet.append_row(row)
        return True
    except Exception as e:
        logging.error(f"Qarz tranzaksiyasini Sheetsga yozishda xato: {e}")
        return False


def write_sale_to_sheets_sync(agent_name: str, product_name: str, qty_kg: float, sale_price: float, total_amount: float, sale_date: str, sale_time: str) -> bool:
    """Agentning savdo tranzaksiyasini dinamik oylik Sheets varag'iga yozadi."""
    spreadsheet = get_sheets_client()
    if not spreadsheet: return False

    try:
        worksheet = get_or_create_monthly_sheet(spreadsheet)
        if not worksheet: return False
        
        row = [
            sale_date,
            sale_time,
            agent_name,
            product_name,
            qty_kg,
            sale_price,
            total_amount
        ]
        worksheet.append_row(row)
        return True
    except Exception as e:
        logging.error(f"Savdo tranzaksiyasini Sheetsga yozishda xato: {e}")
        return False

# ==============================================================================
# IV. ASINXRON PROKSI (PROXY) FUNKSIYALARI
# ==============================================================================
# Boshqa fayllar endi faqat quyidagi funksiyalarni chaqirishi kerak.

async def write_stock_txn_to_sheets(agent_name: str, product_name: str, qty_kg: float, issue_price: float, total_cost: float) -> bool:
    """Sinxron stok yozish funksiyasini bloklanmasdan chaqiradi."""
    return await asyncio.to_thread(
        write_stock_txn_to_sheets_sync, 
        agent_name, product_name, qty_kg, issue_price, total_cost
    )

async def write_debt_txn_to_sheets(agent_name: str, txn_type: str, amount: float, txn_date: str, comment: str) -> bool:
    """Sinxron pul harakati funksiyasini bloklanmasdan chaqiradi."""
    return await asyncio.to_thread(
        write_debt_txn_to_sheets_sync, 
        agent_name, txn_type, amount, txn_date, comment
    )

async def write_sale_to_sheets(agent_name: str, product_name: str, qty_kg: float, sale_price: float, total_amount: float, sale_date: str, sale_time: str) -> bool:
    """Sinxron savdo yozish funksiyasini bloklanmasdan chaqiradi."""
    return await asyncio.to_thread(
        write_sale_to_sheets_sync, 
        agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time
    )
