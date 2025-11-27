# database.py

import asyncpg
import logging
import pandas as pd
import asyncio # Yangi import
from functools import wraps # Yangi import
from config import DATABASE_URL
import sheets_api # Endi u sinxron funksiyalarni o'z ichiga oladi
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global ulanish havzasi (Connection Pool)
DB_POOL: Optional[asyncpg.Pool] = None

# --- Yordamchi Funksiyalar va Dekorator ---

async def init_db_pool() -> Optional[asyncpg.Pool]:
    """Ulanishlar havzasini (Connection Pool) initsializatsiya qiladi."""
    global DB_POOL
    if DB_POOL is None:
        try:
            DB_POOL = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
            logging.info("PostgreSQL ulanish havzasi muvaffaqiyatli initsializatsiya qilindi.")
        except Exception as e:
            logging.error(f"PostgreSQL ulanish havzasini initsializatsiya qilishda xato: {e}")
            DB_POOL = None
    return DB_POOL

def with_connection(func):
    """
    Funksiyani asyncpg ulanish havzasi yordamida ulanishni olish va yakunlash uchun o'raydi (decorator).
    Barcha DB funksiyalari endi bu dekoratordan foydalanadi.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        pool = await init_db_pool()
        if not pool:
            logging.error(f"DB ulanish havzasi mavjud emas. {func.__name__} bekor qilindi.")
            # Natija turi (agar ulanish bo'lmasa) funksiya nomiga qarab qaytariladi
            if func.__name__.startswith(('add_', 'update_', 'create_')):
                return False
            elif func.__name__.startswith('get_all'):
                return []
            else:
                return None if 'optional' in func.__annotations__.get('return', '').lower() else (0.0, 0.0)

        # Pool'dan ulanishni oling va uni funktsiyaga yuboring
        async with pool.acquire() as conn:
            return await func(conn, *args, **kwargs)
    return wrapper

# --- I. Jadvallarni Yaratish ---

async def create_tables() -> bool:
    """Ma'lumotlar bazasi jadvallarini yaratadi (Agar mavjud bo'lmasa)."""
    pool = await init_db_pool()
    if not pool: return False

    async with pool.acquire() as conn:
        try:
            # AGENTS jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_name VARCHAR(255) PRIMARY KEY,
                    region_mfy VARCHAR(100) NOT NULL,
                    phone VARCHAR(50),
                    password VARCHAR(50) NOT NULL,
                    telegram_id BIGINT UNIQUE
                );
            """)

            # PRODUCTS jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    name VARCHAR(255) PRIMARY KEY,
                    price NUMERIC(10, 2) NOT NULL
                );
            """)

            # SALES jadvali (Savdo tranzaksiyalari)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(255) REFERENCES agents(agent_name),
                    product_name VARCHAR(255) REFERENCES products(name),
                    qty_kg NUMERIC(10, 2) NOT NULL,
                    sale_price NUMERIC(10, 2) NOT NULL,
                    total_amount NUMERIC(15, 2) NOT NULL,
                    sale_date DATE NOT NULL,
                    sale_time TIME NOT NULL
                );
            """)
            
            # STOCK jadvali (Qarzni hisoblash uchun Issue_Price bo'yicha)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stock (
                    entry_id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(255) REFERENCES agents(agent_name),
                    product_name VARCHAR(255) REFERENCES products(name),
                    quantity_kg NUMERIC(10, 2) NOT NULL,
                    issue_price NUMERIC(10, 2) NOT NULL,
                    total_cost NUMERIC(15, 2) NOT NULL
                );
            """)

            # DEBT jadvali (Pul to'lovlari)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS debt (
                    debt_id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(255) REFERENCES agents(agent_name),
                    transaction_type VARCHAR(50) NOT NULL, -- 'Qoplash', 'Avans'
                    amount NUMERIC(15, 2) NOT NULL, -- To'lov uchun manfiy, Avans uchun musbat
                    txn_date DATE NOT NULL,
                    comment TEXT
                );
            """)
            logging.info("Barcha jadvallar muvaffaqiyatli yaratildi (yoki mavjud).")
            return True
        except Exception as e:
            logging.error(f"Jadvallarni yaratishda xato: {e}")
            return False

# --- II. Agent Mantig'i ---

@with_connection
async def get_all_agents(conn) -> List[Dict]:
    """Barcha agentlarni MFY va Ism bo'yicha tartiblangan ro'yxatini qaytaradi."""
    try:
        records = await conn.fetch("""
            SELECT region_mfy, agent_name, phone, password, telegram_id
            FROM agents
            ORDER BY region_mfy ASC, agent_name ASC;
        """)
        return [dict(r) for r in records]
    except Exception as e:
        logging.error(f"Agentlar ro'yxatini olishda xato: {e}")
        return []

@with_connection
async def get_agent_by_password(conn, password: str) -> Optional[Dict]:
    """Parol orqali agentni topadi."""
    try:
        record = await conn.fetchrow("""
            SELECT region_mfy, agent_name, phone, password, telegram_id
            FROM agents
            WHERE password = $1;
        """, password)
        return dict(record) if record else None
    except Exception as e:
        logging.error(f"Parol orqali agentni olishda xato: {e}")
        return None
        
@with_connection
async def get_agent_by_telegram_id(conn, telegram_id: int) -> Optional[Dict]:
    """Telegram ID orqali agentni topadi."""
    try:
        record = await conn.fetchrow("""
            SELECT region_mfy, agent_name, phone, password, telegram_id
            FROM agents
            WHERE telegram_id = $1;
        """, telegram_id)
        return dict(record) if record else None
    except Exception as e:
        logging.error(f"Telegram ID orqali agentni olishda xato: {e}")
        return None

@with_connection
async def get_agent_info(conn, agent_name: str) -> Optional[Dict]:
    """Agent nomiga ko'ra uning ma'lumotlarini qaytaradi."""
    try:
        record = await conn.fetchrow("""
            SELECT region_mfy, agent_name, phone, password, telegram_id
            FROM agents
            WHERE agent_name = $1;
        """, agent_name)
        return dict(record) if record else None
    except Exception as e:
        logging.error(f"Agent ma'lumotlarini olishda xato: {e}")
        return None

@with_connection
async def add_new_agent(conn, region: str, name: str, phone: str, password: str) -> bool:
    """Yangi agentni bazaga kiritadi."""
    try:
        await conn.execute("""
            INSERT INTO agents (region_mfy, agent_name, phone, password)
            VALUES ($1, $2, $3, $4);
        """, region, name, phone, password)
        return True
    except asyncpg.exceptions.UniqueViolationError:
        logging.warning(f"Agent {name} allaqachon mavjud.")
        return False
    except Exception as e:
        logging.error(f"Yangi agent qo'shishda xato: {e}")
        return False

@with_connection
async def update_agent_telegram_id(conn, agent_name: str, telegram_id: int) -> bool:
    """Agent nomiga ko'ra uning Telegram ID'sini yangilaydi (Login vaqti)."""
    try:
        result = await conn.execute("""
            UPDATE agents
            SET telegram_id = $1
            WHERE agent_name = $2;
        """, telegram_id, agent_name)
        return result == 'UPDATE 1'
    except Exception as e:
        logging.error(f"Agent Telegram ID'sini yangilashda xato: {e}")
        return False


# --- III. Mahsulot Mantig'i ---

@with_connection
async def get_all_products(conn) -> List[Dict]:
    """Barcha mahsulotlar ro'yxatini (nomi va narxi) qaytaradi."""
    try:
        records = await conn.fetch("""
            SELECT name, price
            FROM products
            ORDER BY name ASC;
        """)
        return [dict(r) for r in records]
    except Exception as e:
        logging.error(f"Mahsulotlar ro'yxatini olishda xato: {e}")
        return []

@with_connection
async def get_product_info(conn, product_name: str) -> Optional[Dict]:
    """Mahsulot nomiga ko'ra uning ma'lumotlarini qaytaradi."""
    try:
        record = await conn.fetchrow("""
            SELECT name, price
            FROM products
            WHERE name = $1;
        """, product_name)
        return dict(record) if record else None
    except Exception as e:
        logging.error(f"Mahsulot ma'lumotlarini olishda xato: {e}")
        return None

@with_connection
async def add_new_product(conn, name: str, price: float) -> bool:
    """Yangi mahsulotni bazaga kiritadi."""
    try:
        await conn.execute("""
            INSERT INTO products (name, price)
            VALUES ($1, $2);
        """, name, price)
        return True
    except asyncpg.exceptions.UniqueViolationError:
        logging.warning(f"Mahsulot {name} allaqachon mavjud.")
        return False
    except Exception as e:
        logging.error(f"Yangi mahsulot qo'shishda xato: {e}")
        return False

@with_connection
async def update_product_price(conn, product_name: str, new_price: float) -> bool:
    """Mahsulot narxini yangilaydi."""
    try:
        result = await conn.execute("""
            UPDATE products
            SET price = $1
            WHERE name = $2;
        """, new_price, product_name)
        return result == 'UPDATE 1'
    except Exception as e:
        logging.error(f"Mahsulot narxini yangilashda xato: {e}")
        return False

# --- IV. Hisob-kitob Mantig'i ---

@with_connection
async def calculate_agent_stock(conn, agent_name: str) -> List[Dict]:
    """
    Agentdagi har bir mahsulot bo'yicha qoldiq miqdorini (KG) hisoblaydi (Berilgan - Sotilgan).
    """
    try:
        # Mahsulotlarni Berish (STOCK) va Sotish (SALES) operatsiyalarini birlashtirish
        records = await conn.fetch("""
            WITH StockIn AS (
                SELECT 
                    product_name, 
                    COALESCE(SUM(quantity_kg), 0) AS total_received
                FROM stock
                WHERE agent_name = $1
                GROUP BY product_name
            ),
            SalesOut AS (
                SELECT 
                    product_name, 
                    COALESCE(SUM(qty_kg), 0) AS total_sold
                FROM sales
                WHERE agent_name = $1
                GROUP BY product_name
            )
            SELECT
                p.name AS product_name,
                COALESCE(si.total_received, 0) AS received_qty,
                COALESCE(so.total_sold, 0) AS sold_qty,
                COALESCE(si.total_received, 0) - COALESCE(so.total_sold, 0) AS balance_qty
            FROM products p
            LEFT JOIN StockIn si ON p.name = si.product_name
            LEFT JOIN SalesOut so ON p.name = so.product_name
            -- Agentga berilgan yoki sotilgan mahsulotlarni filtrlaymiz
            WHERE COALESCE(si.total_received, 0) > 0 OR COALESCE(so.total_sold, 0) > 0
            ORDER BY p.name ASC;
        """, agent_name)
        
        return [dict(r) for r in records]
        
    except Exception as e:
        logging.error(f"Agent stogini hisoblashda xato: {e}")
        return []

@with_connection
async def calculate_agent_debt(conn, agent_name: str) -> Tuple[float, float]:
    """Agentning jami qarzdorligi (musbat) va haqdorligi (manfiy) ni hisoblaydi."""
    
    current_debt = 0.0
    
    try:
        # 1. STOK qiymati (Agentning boshlang'ich qarzi - total_cost)
        stock_cost = await conn.fetchval("""
            SELECT COALESCE(SUM(total_cost), 0)
            FROM stock
            WHERE agent_name = $1;
        """, agent_name)
        current_debt += float(stock_cost)
        
        # 2. QARZDORLIK tranzaksiyalari (To'lovlar/Avanslar - Amount)
        debt_amount = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0)
            FROM debt
            WHERE agent_name = $1;
        """, agent_name)
        current_debt += float(debt_amount)

        # Natijani ajratish:
        if current_debt >= 0:
            return current_debt, 0.0 # Qarzdorlik (Agent qarz), Haqdorlik (0)
        else:
            return 0.0, abs(current_debt) # Qarzdorlik (0), Haqdorlik (Kompaniya qarz)
            
    except Exception as e:
        logging.error(f"Agent qarzini hisoblashda xato: {e}")
        return 0.0, 0.0

# --- V. Ma'lumot Kiritish Mantig'i (SQL + Sheets Sinkronlash) ---

@with_connection
async def add_stock_transaction(conn, agent_name: str, product_name: str, qty_kg: float, issue_price: float) -> bool:
    """Agentga tovar berish amaliyotini yozadi va Sheetsga sinkronlaydi."""
    
    total_cost = qty_kg * issue_price
    
    try:
        # 1. PostgreSQL ga yozish
        await conn.execute("""
            INSERT INTO stock (agent_name, product_name, quantity_kg, issue_price, total_cost)
            VALUES ($1, $2, $3, $4, $5);
        """, agent_name, product_name, qty_kg, issue_price, total_cost)
        
        # 2. Sheetsga yozish (ASOSIY SINKRONLASh - Asinxron muhitni bloklamaslik uchun to_thread() ishlatiladi)
        await asyncio.to_thread(sheets_api.write_stock_txn_to_sheets, agent_name, product_name, qty_kg, issue_price, total_cost)
        
        return True
    except Exception as e:
        logging.error(f"Stok tranzaksiyasini qo'shishda xato: {e}")
        return False
        
@with_connection
async def add_debt_payment(conn, agent_name: str, amount: float, comment: str, is_payment: bool = True) -> bool:
    """Agent tomonidan pul to'lash/avans berish amaliyotini yozadi va Sheetsga sinkronlaydi."""

    final_amount = -amount if is_payment else amount
    txn_type = "Qoplash" if is_payment else "Avans"
    txn_date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # 1. PostgreSQL ga yozish
        await conn.execute("""
            INSERT INTO debt (agent_name, transaction_type, amount, txn_date, comment)
            VALUES ($1, $2, $3, $4, $5);
        """, agent_name, txn_type, final_amount, txn_date, comment)
        
        # 2. Sheetsga yozish (ASOSIY SINKRONLASh)
        await asyncio.to_thread(sheets_api.write_debt_txn_to_sheets, agent_name, txn_type, final_amount, txn_date, comment)
        
        return True
    except Exception as e:
        logging.error(f"Qarz to'lovini/Avansni qo'shishda xato: {e}")
        return False

@with_connection
async def add_sales_transaction(conn, agent_name: str, product_name: str, qty_kg: float, sale_price: float) -> bool:
    """Agentning savdo tranzaksiyasini yozadi va Sheetsga sinkronlaydi (oylik varaq)."""

    total_amount = qty_kg * sale_price
    now = datetime.now()
    sale_date = now.strftime("%Y-%m-%d")
    sale_time = now.strftime("%H:%M:%S")

    try:
        # 1. PostgreSQL ga yozish
        await conn.execute("""
            INSERT INTO sales (agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
        """, agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time)
        
        # 2. Sheetsga yozish (ASOSIY SINKRONLASh - Dinamik oylik varaqqa)
        await asyncio.to_thread(sheets_api.write_sale_to_sheets, agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time)

        return True
    except Exception as e:
        logging.error(f"Savdo tranzaksiyasini qo'shishda xato: {e}")
        return False

# --- VI. KUNLIK SAVDO PIVOT HISOBOTI (Monospace) ---

@with_connection
async def get_daily_sales_pivot_report(conn) -> Optional[str]:
    """
    Kunlik savdo ma'lumotlarini bazadan oladi va monospace formatda chiqaradi.
    """
    try:
        # 1. Barcha sotuv va agent ma'lumotlarini olish
        records = await conn.fetch("""
            SELECT
                s.agent_name,
                a.region_mfy,
                s.qty_kg,
                s.sale_date
            FROM sales s
            JOIN agents a ON s.agent_name = a.agent_name
            ORDER BY s.sale_date DESC;
        """)
        
        if not records: return "⚠️ Savdo ma'lumotlari topilmadi."

        # 2. Pandas DataFrame yaratish
        df = pd.DataFrame([dict(r) for r in records])

        # 3. Ustunlarni tayyorlash
        df.rename(columns={'region_mfy': 'MFY_Nomi', 'agent_name': 'Agent_Ismi', 'qty_kg': 'Qty_KG'}, inplace=True)
        df['Qty_KG'] = pd.to_numeric(df['Qty_KG'], errors='coerce').fillna(0)
        df['sale_date'] = pd.to_datetime(df['sale_date'], errors='coerce').dt.strftime('%m-%d')
        
        # 4. Pivot jadvalni yaratish (Sana ustun)
        pivot_df = pd.pivot_table(
            df, 
            values='Qty_KG', 
            index=['MFY_Nomi', 'Agent_Ismi'], 
            columns='sale_date', 
            aggfunc='sum', 
            fill_value=0.0
        )
        
        # 5. 'Jami Savdo' ustunini qo'shish
        pivot_df['Jami_Savdo'] = pivot_df.sum(axis=1)

        # 6. Tartiblash (MFY keyin Agent nomi bo'yicha)
        pivot_df = pivot_df.sort_values(by=['MFY_Nomi', 'Agent_Ismi'], ascending=[True, True])
        
        # 7. Ustunlarni tartibga keltirish
        date_cols = [col for col in pivot_df.columns if col not in ['MFY_Nomi', 'Agent_Ismi', 'Jami_Savdo']]
        date_cols.sort()
        
        # Faqat so'nggi 7 kunlik ma'lumotni olish uchun
        date_cols = date_cols[-7:] 
        
        final_cols = ['Jami_Savdo'] + date_cols
        pivot_df = pivot_df.reset_index()

        # 8. Matnni Monospace formatida shakllantirish
        
        # Ustun kengliklarini hisoblash
        col_widths = {
            'MFY_Nomi': max(pivot_df['MFY_Nomi'].astype(str).str.len().max() or 8, 8),
            'Agent_Ismi': max(pivot_df['Agent_Ismi'].astype(str).str.len().max() or 12, 12),
            'Jami_Savdo': 10 # 1234.5 kg
        }
        for col in date_cols:
            col_widths[col] = 7 # 01-01 format + .1f

        report_lines = []
        
        # --- Sarlavha (Head) ---
        header_line = ""
        header_line += "MFY NOMI".ljust(col_widths['MFY_Nomi']) + " | "
        header_line += "AGENT ISMI".ljust(col_widths['Agent_Ismi']) + " | "
        header_line += "JAMI SAVDO".rjust(col_widths['Jami_Savdo'])
        
        for col in date_cols:
            header_line += " | " + col.center(col_widths[col])
            
        report_lines.append(header_line)
        
        # --- Ajratuvchi chiziq ---
        separator = "-" * len(header_line)
        report_lines.append(separator)

        # --- Ma'lumot Qatorlari ---
        for index, row in pivot_df.iterrows():
            line = ""
            line += str(row['MFY_Nomi']).ljust(col_widths['MFY_Nomi']) + " | "
            line += str(row['Agent_Ismi']).ljust(col_widths['Agent_Ismi']) + " | "
            
            # Raqamni formatlashda 1 o'nli kasr kerak
            jami_savdo_kg = f"{row['Jami_Savdo']:.1f} kg"
            line += jami_savdo_kg.rjust(col_widths['Jami_Savdo']) 
            
            for col in date_cols:
                qty_val = f"{row[col]:.1f}"
                line += " | " + qty_val.rjust(col_widths[col])
                
            report_lines.append(line)

        # --- Jami Yig'indi Qatori (Total Sum) ---
        total_sum = pivot_df['Jami_Savdo'].sum()
        
        # Yig'indi qatorini matn bilan chiqarish
        total_line = ""
        total_line += "Yig'indi".ljust(col_widths['MFY_Nomi']) + " | "
        total_line += "JAMI".ljust(col_widths['Agent_Ismi']) + " | "
        total_line += f"{total_sum:.1f} kg".rjust(col_widths['Jami_Savdo'])
        
        # Yig'indi sanalar bo'yicha
        for col in date_cols:
            daily_sum = pivot_df[col].sum()
            total_line += " | " + f"{daily_sum:.1f}".rjust(col_widths[col])
            
        report_lines.append(separator)
        report_lines.append(total_line)


        final_report = "📊 **Kunlik Savdo Hisoboti** (KG):\n\n"
        final_report += "```\n"
        final_report += "\n".join(report_lines)
        final_report += "\n```"
        
        return final_report
        
    except Exception as e:
        logging.error(f"Pivot hisobotini yaratishda xato: {e}")
        return f"⚠️ Hisobotni tayyorlashda ichki xato yuz berdi: {e}"
