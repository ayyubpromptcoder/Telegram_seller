import asyncpg
import logging
import polars as pl # Y A N G I: polars qo'shiladi
import asyncio
from functools import wraps
from config import DATABASE_URL
import sheets_api
from typing import List, Dict, Tuple, Optional
# datetime kutubxonalarini import qilish
from datetime import datetime, timedelta, date # date qo'shildi

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global PostgreSQL ulanish havzasi (Connection Pool)
DB_POOL: Optional[asyncpg.Pool] = None

# --- Yordamchi Funksiyalar va Dekorator ---

async def init_db_pool() -> Optional[asyncpg.Pool]:
    """Ulanishlar havzasini (Connection Pool) initsializatsiya qiladi. Global DB_POOL ni o'rnatadi."""
    global DB_POOL
    if DB_POOL is None:
        try:
            # min_size va max_size ulanishlar sonini belgilaydi
            DB_POOL = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
            logging.info("PostgreSQL ulanish havzasi muvaffaqiyatli initsializatsiya qilindi.")
        except Exception as e:
            logging.error(f"PostgreSQL ulanish havzasini initsializatsiya qilishda xato: {e}")
            DB_POOL = None
    return DB_POOL

def with_connection(func):
    """
    Asinxron funksiyani asyncpg ulanish havzasidan ulanishni olish va yakunlash uchun o'raydi (decorator).
    Barcha DB mantiqiy funksiyalari ushbu dekoratordan foydalanishi kerak.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        pool = await init_db_pool()
        if not pool:
            logging.error(f"DB ulanish havzasi mavjud emas. {func.__name__} bekor qilindi.")
            # Ulanish bo'lmasa, funksiya turiga mos keluvchi sukut qiymatni qaytarish
            if func.__name__.startswith(('add_', 'update_', 'create_')):
                return False
            elif func.__name__.startswith('get_all'):
                return []
            else:
                # Agar funksiya tuple (masalan, qarz) yoki Dict/None qaytarsa
                return None if 'optional' in func.__annotations__.get('return', '').lower() else (0.0, 0.0)

        # Pool'dan ulanishni oling va uni funktsiyaga birinchi argument sifatida yuboring (conn)
        async with pool.acquire() as conn:
            # Dekoratsiyalangan funksiyani 'conn' bilan chaqirish
            return await func(conn, *args, **kwargs)
    return wrapper

# --- I. Jadvallarni Yaratish ---

async def create_tables() -> bool:
    """Ma'lumotlar bazasi jadvallarini yaratadi (Agar mavjud bo'lmasa)."""
    pool = await init_db_pool()
    if not pool: return False

    async with pool.acquire() as conn:
        try:
            # AGENTS jadvali: Agent ma'lumotlari
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_name VARCHAR(255) PRIMARY KEY,
                    region_mfy VARCHAR(100) NOT NULL,
                    phone VARCHAR(50),
                    password VARCHAR(50) NOT NULL,
                    telegram_id BIGINT UNIQUE
                );
            """)

            # PRODUCTS jadvali: Sotuvga chiqariladigan mahsulotlar ro'yxati va standart narxi
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    name VARCHAR(255) PRIMARY KEY,
                    price NUMERIC(10, 2) NOT NULL
                );
            """)

            # SALES jadvali: Agent tomonidan amalga oshirilgan savdo tranzaksiyalari (Tashqi narx)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    sale_id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(255) REFERENCES agents(agent_name),
                    product_name VARCHAR(255) REFERENCES products(name),
                    qty_kg NUMERIC(10, 2) NOT NULL,
                    sale_price NUMERIC(10, 2) NOT NULL, -- Sotilgan narx
                    total_amount NUMERIC(15, 2) NOT NULL,
                    sale_date DATE NOT NULL,
                    sale_time TIME NOT NULL
                );
            """)
            
            # STOCK jadvali: Agentga tovar berish (Ichki narx - Qarz hisobining boshlang'ich nuqtasi)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stock (
                    entry_id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(255) REFERENCES agents(agent_name),
                    product_name VARCHAR(255) REFERENCES products(name),
                    quantity_kg NUMERIC(10, 2) NOT NULL,
                    issue_price NUMERIC(10, 2) NOT NULL, -- Chiqarish narxi (kompaniya uchun tannarx/bahosi)
                    total_cost NUMERIC(15, 2) NOT NULL
                );
            """)

            # DEBT jadvali: Pul to'lovlari (Qoplash, Avans)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS debt (
                    debt_id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(255) REFERENCES agents(agent_name),
                    transaction_type VARCHAR(50) NOT NULL, -- 'Qoplash', 'Avans'
                    amount NUMERIC(15, 2) NOT NULL, 
                    -- Eslatma: 'Qoplash' uchun manfiy, 'Avans' uchun musbat (Agentning balansi oshadi, ya'ni bu yerda 'Avans' agentning naqd pul yechib olishi deb faraz qilingan).
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
    Faqat agentga berilgan yoki sotilgan mahsulotlarni ko'rsatadi.
    """
    try:
        # StockIn: Agentga berilgan jami miqdor (quantity_kg)
        # SalesOut: Agent sotgan jami miqdor (qty_kg)
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
            LEFT JOIN SalesOut so ON p.name = so.product_JOIN product_name
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
    """
    Agentning jami qarzdorligi (musbat) va haqdorligi (manfiy) ni hisoblaydi.
    Qarzdorlik = Sum(Stock Cost) + Sum(Debt Amounts)
    """
    
    current_debt = 0.0 # Agentning kompaniyaga jami qarzi (musbat bo'lsa qarz, manfiy bo'lsa kompaniya qarz)
    
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
            # Agar umumiy summa musbat yoki nol bo'lsa, bu Agentning qarzi
            return current_debt, 0.0 # Qarzdorlik (Agent qarz), Haqdorlik (0)
        else:
            # Agar umumiy summa manfiy bo'lsa, bu Kompaniyaning Agentga bo'lgan qarzi
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
        # 1. PostgreSQL ga yozish (Atomik operatsiya)
        await conn.execute("""
            INSERT INTO stock (agent_name, product_name, quantity_kg, issue_price, total_cost)
            VALUES ($1, $2, $3, $4, $5);
        """, agent_name, product_name, qty_kg, issue_price, total_cost)
        
        # 2. Sheetsga yozish (ASOSIY SINKRONLASh)
        # Sinxron Sheets API chaqiruvini asinxron muhitni bloklamaslik uchun to_thread() yordamida ajratish
        await asyncio.to_thread(sheets_api.write_stock_txn_to_sheets, agent_name, product_name, qty_kg, issue_price, total_cost)
        
        return True
    except Exception as e:
        logging.error(f"Stok tranzaksiyasini qo'shishda xato: {e}")
        return False
        
@with_connection
async def add_debt_payment(conn, agent_name: str, amount: float, comment: str, is_payment: bool = True) -> bool:
    """Agent tomonidan pul to'lash/avans berish amaliyotini yozadi va Sheetsga sinkronlaydi."""

    # Agar bu Qoplash (Payment) bo'lsa, summa manfiy qilinadi (qarzdorlikni kamaytiradi)
    final_amount = -amount if is_payment else amount 
    txn_type = "Qoplash" if is_payment else "Avans"
    # ❌ XATO TUZATILDI: SQL ga DATE tipida uzatish uchun .date() ishlatildi.
    txn_date = datetime.now().date() 
    
    try:
        # 1. PostgreSQL ga yozish
        await conn.execute("""
            INSERT INTO debt (agent_name, transaction_type, amount, txn_date, comment)
            VALUES ($1, $2, $3, $4, $5);
        """, agent_name, txn_type, final_amount, txn_date, comment)
        
        # 2. Sheetsga yozish (ASOSIY SINKRONLASh)
        # Sheetsga matn formatida (str) yozish uchun formatlash kerak bo'lishi mumkin.
        txn_date_str = txn_date.strftime("%Y-%m-%d")
        await asyncio.to_thread(sheets_api.write_debt_txn_to_sheets, agent_name, txn_type, final_amount, txn_date_str, comment)
        
        return True
    except Exception as e:
        logging.error(f"Qarz to'lovini/Avansni qo'shishda xato: {e}")
        return False

@with_connection
async def add_sales_transaction(conn, agent_name: str, product_name: str, qty_kg: float, sale_price: float) -> bool:
    """Agentning savdo tranzaksiyasini yozadi va Sheetsga sinkronlaydi (oylik varaq)."""

    total_amount = qty_kg * sale_price
    now = datetime.now()
    # ❌ XATO TUZATILDI: SQL ga DATE tipida uzatish uchun .date() ishlatildi.
    sale_date = now.date()
    sale_time = now.time() # TIME uchun
    
    try:
        # 1. PostgreSQL ga yozish
        await conn.execute("""
            INSERT INTO sales (agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
        """, agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time)
        
        # 2. Sheetsga yozish (ASOSIY SINKRONLASh - Dinamik oylik varaqqa)
        sale_date_str = sale_date.strftime("%Y-%m-%d")
        sale_time_str = sale_time.strftime("%H:%M:%S")
        await asyncio.to_thread(sheets_api.write_sale_to_sheets, agent_name, product_name, qty_kg, sale_price, total_amount, sale_date_str, sale_time_str)

        return True
    except Exception as e:
        logging.error(f"Savdo tranzaksiyasini qo'shishda xato: {e}")
        return False

# --- VI. KUNLIK SAVDO PIVOT HISOBOTI (Monospace) ---

# database.py

# --- VI. KUNLIK SAVDO PIVOT HISOBOTI (Monospace) ---

@with_connection
async def get_daily_sales_pivot_report(conn) -> Optional[str]:
    """
    Kunlik savdo ma'lumotlarini bazadan oladi, Polars yordamida pivot qiladi va Telegram uchun qulay monospace formatda chiqaradi.
    Faqat oxirgi 31 kunlik ma'lumotni ko'rsatadi.
    """
    try:
        # 1. Barcha sotuv va agent ma'lumotlarini olish
        # ❌ XATO TUZATILDI: PostgreSQL ga uzatishdan oldin .date() ishlatildi.
        thirty_one_days_ago = (datetime.now() - timedelta(days=31)).date()
        
        records = await conn.fetch("""
            SELECT
                s.agent_name,
                a.region_mfy,
                s.qty_kg,
                s.sale_date
            FROM sales s
            JOIN agents a ON s.agent_name = a.agent_name
            WHERE s.sale_date >= $1  
            ORDER BY s.sale_date DESC;
        """, thirty_one_days_ago) # SQL filteri orqali tezlashtirish

        if not records: return "⚠️ Savdo ma'lumotlari oxirgi 31 kun ichida topilmadi."

        # 2. Polars DataFrame yaratish
        data = [dict(r) for r in records]
        df = pl.DataFrame(data)

        # 3. Ustunlarni qayta nomlash va ma'lumot turlarini sozlash
        df = df.rename({'region_mfy': 'MFY_Nomi', 'agent_name': 'Agent_Ismi', 'qty_kg': 'Qty_KG'})
        
        df = df.with_columns(
            pl.col('Qty_KG').cast(pl.Float64, strict=False).fill_null(0.0),
            pl.col('sale_date').cast(pl.Date, strict=False)
        )
        
        # Sanani 'MM-DD' formatiga o'tkazish uchun yangi ustun yaratish
        df = df.with_columns(
            pl.col('sale_date').dt.strftime('%m-%d').alias('Day_MMDD')
        )
        
        # 4. Pivot jadvalni yaratish (Polars Pivot usuli)
        pivot_df = df.pivot(
            index=['MFY_Nomi', 'Agent_Ismi'], 
            columns='Day_MMDD', 
            values='Qty_KG', 
            aggregate_function='sum',
            fill_value=0.0
        ).collect() # eager() chaqiruviga o'xshash
        
        # 5. 'Jami Savdo' ustunini qo'shish
        date_cols_temp = [col for col in pivot_df.columns if col not in ['MFY_Nomi', 'Agent_Ismi']]
        
        pivot_df = pivot_df.with_columns(
            pl.sum_horizontal(pl.col(date_cols_temp)).alias('Jami_Savdo')
        )

        # 6. Tartiblash
        pivot_df = pivot_df.sort(['MFY_Nomi', 'Agent_Ismi'], descending=[False, False])
        
        # 7. Ustunlarni tartibga keltirish (Barcha 31 kunlik ustunlar olinadi)
        date_cols = [col for col in pivot_df.columns if col not in ['MFY_Nomi', 'Agent_Ismi', 'Jami_Savdo']]
        date_cols.sort() # Eski sanadan yangi sanaga tartiblash

        final_cols_order = ['MFY_Nomi', 'Agent_Ismi', 'Jami_Savdo'] + date_cols
        pivot_df = pivot_df.select(final_cols_order)

        data_rows = pivot_df.to_dict(as_series=False) 
        
        # 8. Matnni Monospace formatida shakllantirish
        
        # [UZGARISH: 31 KUN UCHUN QISQARTIRILGAN USTUN KENGILIKLARI]
        col_widths = {
            'MFY_Nomi': min(max(max(len(str(x)) for x in data_rows['MFY_Nomi']) if data_rows['MFY_Nomi'] else 8, 8), 10),
            'Agent_Ismi': min(max(max(len(str(x)) for x in data_rows['Agent_Ismi']) if data_rows['Agent_Ismi'] else 12, 12), 15),
            'Jami_Savdo': 8 
        }
        for col in date_cols:
            col_widths[col] = 5 # Sanalar uchun 5 belgiga qisqartirildi (MM-DD)
        
        report_lines = []
        
        # --- Sarlavha (Head) ---
        header_line = ""
        header_line += "MFY NOMI".ljust(col_widths['MFY_Nomi']) + " | "
        header_line += "AGENT ISMI".ljust(col_widths['Agent_Ismi']) + " | "
        header_line += "JAMI".rjust(col_widths['Jami_Savdo'])
        
        for col in date_cols:
            header_line += " | " + col.center(col_widths[col])
            
        report_lines.append(header_line)
        
        # --- Ajratuvchi chiziq ---
        separator = "-" * len(header_line)
        report_lines.append(separator)

        # --- Ma'lumot Qatorlari ---
        for i in range(len(data_rows['MFY_Nomi'])):
            line = ""
            mfy_name = data_rows['MFY_Nomi'][i]
            agent_name = data_rows['Agent_Ismi'][i]
            jami_savdo = data_rows['Jami_Savdo'][i]
            
            line += str(mfy_name).ljust(col_widths['MFY_Nomi']) + " | "
            line += str(agent_name).ljust(col_widths['Agent_Ismi']) + " | "
            
            # Raqamni formatlash (1 o'nli kasr)
            jami_savdo_kg = f"{jami_savdo:.1f}"
            line += jami_savdo_kg.rjust(col_widths['Jami_Savdo'])
            
            for col in date_cols:
                qty_val = data_rows.get(col, [0.0] * len(data_rows['MFY_Nomi']))[i]
                qty_val_formatted = f"{qty_val:.1f}"
                line += " | " + qty_val_formatted.rjust(col_widths[col])
                    
            report_lines.append(line)

        # --- Jami Yig'indi Qatori (Total Sum) ---
        total_sum = sum(data_rows['Jami_Savdo'])
        
        total_line = ""
        total_line += "Yig'indi".ljust(col_widths['MFY_Nomi']) + " | "
        total_line += "JAMI".ljust(col_widths['Agent_Ismi']) + " | "
        total_line += f"{total_sum:.1f}".rjust(col_widths['Jami_Savdo'])
        
        for col in date_cols:
            daily_sum = sum(data_rows.get(col, [0.0] * len(data_rows['MFY_Nomi'])))
            total_line += " | " + f"{daily_sum:.1f}".rjust(col_widths[col])
            
        report_lines.append(separator)
        report_lines.append(total_line)


        final_report = f"📊 **Oxirgi Oylik ({len(date_cols)} kunlik) Savdo Hisoboti** ({datetime.now().strftime('%Y-%m-%d')} holatiga):\n\n"
        final_report += "```\n"
        final_report += "\n".join(report_lines)
        final_report += "\n```"
        
        return final_report
        
    except Exception as e:
        logging.error(f"Polars 31 kunlik Pivot hisobotini yaratishda xato: {e}")
        return f"⚠️ Hisobotni tayyorlashda ichki xato yuz berdi: {e}"
