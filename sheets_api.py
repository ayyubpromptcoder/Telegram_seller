# sheets_api.py

# ==============================================================================
# I. KERAKLI KUTUBXONALAR VA ULANISH
# ==============================================================================

import gspread
import logging
from google.oauth2.service_account import Credentials
from config import SPREADSHEET_ID, SERVICE_ACCOUNT_FILE, SHEET_NAMES
from datetime import datetime

logging.basicConfig(level=logging.INFO)

def get_sheets_client():
    """Google Sheetsga ulanishni ta'minlaydi."""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return spreadsheet
    except Exception as e:
        logging.error(f"Google Sheetsga ulanishda xato: {e}")
        return None

# ==============================================================================
# II. VANAQ BILAN ISHLASH MANTIG'I
# ==============================================================================

def get_or_create_monthly_sales_sheet() -> Optional[gspread.Worksheet]:
    """
    Joriy oy uchun Sheets varaqini topadi (YYYY-MM). Agar mavjud bo'lmasa, yaratadi.
    """
    spreadsheet = get_sheets_client()
    if not spreadsheet: return None
    
    # Joriy yil va oyga asoslangan varaq nomi
    sheet_title = datetime.now().strftime("%Y-%m")
    
    try:
        # 1. Mavjud varaqni qidirish
        try:
            worksheet = spreadsheet.worksheet(sheet_title)
            logging.info(f"Sheets: '{sheet_title}' varag'i topildi.")
            return worksheet
        except gspread.WorksheetNotFound:
            logging.info(f"Sheets: '{sheet_title}' varag'i topilmadi. Yaratilmoqda...")
            
            # 2. Yangi varaq yaratish
            worksheet = spreadsheet.add_worksheet(title=sheet_title, rows=1000, cols=10)
            
            # 3. Ustun sarlavhalarini o'rnatish (SALES varag'i tuzilmasi asosida)
            headers = [
                "Agent_Name", "Product_Name", "Qty_KG", "Sale_Price", 
                "Total_Amount", "Date", "Time"
            ]
            worksheet.append_row(headers, value_input_option='USER_ENTERED')
            logging.info(f"Sheets: '{sheet_title}' varag'i va sarlavhalar yaratildi.")
            return worksheet

    except Exception as e:
        logging.error(f"Sheets varag'ini boshqarishda xato: {e}")
        return None

def write_sale_to_sheets(agent_name: str, product_name: str, qty_kg: float, sale_price: float, total_amount: float, date: str, time: str) -> bool:
    """
    Savdo tranzaksiyasini joriy oylik Sheets varag'iga yozadi.
    """
    worksheet = get_or_create_monthly_sales_sheet()
    if not worksheet: return False

    try:
        # Ma'lumot qatori
        row = [
            agent_name, 
            product_name, 
            qty_kg, 
            sale_price, 
            total_amount, 
            date, 
            time
        ]
        
        # Sheetsga yozish
        worksheet.append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        logging.error(f"Savdoni Sheetsga yozishda xato: {e}")
        return False

# ==============================================================================
# III. BOSHQA TRANZAKSIYALARNI YOZISH (Qo'shimcha)
# ==============================================================================

async def write_stock_txn_to_sheets(agent_name: str, product_name: str, qty_kg: float, issue_price: float, total_cost: float) -> bool:
    """Agentga tovar berishni umumiy STOK varag'iga yozadi."""
    spreadsheet = get_sheets_client()
    if not spreadsheet: return False
    
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAMES["STOCK"])
        row = [agent_name, product_name, qty_kg, issue_price, total_cost]
        worksheet.append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        logging.error(f"Stokni Sheetsga yozishda xato: {e}")
        return False

async def write_debt_txn_to_sheets(agent_name: str, txn_type: str, amount: float, txn_date: str, comment: str) -> bool:
    """Agent to'lovini/avansini umumiy QARZDORLIK varag'iga yozadi."""
    spreadsheet = get_sheets_client()
    if not spreadsheet: return False
    
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAMES["DEBT"])
        row = [agent_name, txn_type, amount, txn_date, comment]
        worksheet.append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        logging.error(f"Qarzni Sheetsga yozishda xato: {e}")
        return False
