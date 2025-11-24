# database.py

import asyncpg
import logging
from config import DATABASE_URL
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import pandas as pd

logging.basicConfig(level=logging.INFO)

# --- I. Ulanishni Boshqarish ---

async def connect_db():
    """PostgreSQLga ulanishni ta'minlaydi."""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logging.error(f"PostgreSQLga ulanishda xato: {e}")
        return None

async def create_tables():
    """Ma'lumotlar bazasi jadvallarini yaratadi (Agar mavjud bo'lmasa)."""
    conn = await connect_db()
    if not conn: return False

    try:
        # AGENTS jadvali (Agent_Name - asosiy kalit)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_name VARCHAR(255) PRIMARY KEY,
                region_mfy VARCHAR(100) NOT NULL,
                phone VARCHAR(50),
                password VARCHAR(50) NOT NULL
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
    finally:
        await conn.close() if conn else None

# --- II. Agent Mantig'i (SQL versiyasi) ---

async def get_all_agents() -> List[Dict]:
    """Barcha agentlarni MFY va Ism bo'yicha tartiblangan ro'yxatini qaytaradi."""
    conn = await connect_db()
    if not conn: return []
    try:
        # MFY va Agent_Name bo'yicha tartiblash talabi bajariladi
        records = await conn.fetch("""
            SELECT region_mfy, agent_name, phone, password
            FROM agents
            ORDER BY region_mfy ASC, agent_name ASC;
        """)
        return [dict(r) for r in records]
    except Exception as e:
        logging.error(f"Agentlar ro'yxatini olishda xato: {e}")
        return []
    finally:
        await conn.close() if conn else None

async def get_agent_by_password(password: str) -> Optional[Dict]:
    """Parol orqali agentni topadi."""
    conn = await connect_db()
    if not conn: return None
    try:
        record = await conn.fetchrow("""
            SELECT region_mfy, agent_name, phone, password
            FROM agents
            WHERE password = $1;
        """, password)
        return dict(record) if record else None
    except Exception as e:
        logging.error(f"Parol orqali agentni olishda xato: {e}")
        return None
    finally:
        await conn.close() if conn else None

async def get_agent_info(agent_name: str) -> Optional[Dict]:
    """Agent nomiga ko'ra uning ma'lumotlarini qaytaradi."""
    conn = await connect_db()
    if not conn: return None
    try:
        record = await conn.fetchrow("""
            SELECT region_mfy, agent_name, phone, password
            FROM agents
            WHERE agent_name = $1;
        """, agent_name)
        return dict(record) if record else None
    except Exception as e:
        logging.error(f"Agent ma'lumotlarini olishda xato: {e}")
        return None
    finally:
        await conn.close() if conn else None

async def add_new_agent(region: str, name: str, phone: str, password: str) -> bool:
    """Yangi agentni bazaga kiritadi."""
    conn = await connect_db()
    if not conn: return False
    try:
        await conn.execute("""
            INSERT INTO agents (region_mfy, agent_name, phone, password)
            VALUES ($1, $2, $3, $4);
        """, region, name, phone, password)
        return True
    except Exception as e:
        logging.error(f"Yangi agent qo'shishda xato: {e}")
        return False
    finally:
        await conn.close() if conn else None

# --- III. Mahsulot Mantig'i (SQL versiyasi) ---

async def get_all_products() -> List[Dict]:
    """Barcha mahsulotlar ro'yxatini (nomi va narxi) qaytaradi."""
    conn = await connect_db()
    if not conn: return []
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
    finally:
        await conn.close() if conn else None

async def get_product_info(product_name: str) -> Optional[Dict]:
    """Mahsulot nomiga ko'ra uning ma'lumotlarini qaytaradi."""
    conn = await connect_db()
    if not conn: return None
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
    finally:
        await conn.close() if conn else None

async def add_new_product(name: str, price: float) -> bool:
    """Yangi mahsulotni bazaga kiritadi."""
    conn = await connect_db()
    if not conn: return False
    try:
        await conn.execute("""
            INSERT INTO products (name, price)
            VALUES ($1, $2);
        """, name, price)
        return True
    except Exception as e:
        logging.error(f"Yangi mahsulot qo'shishda xato: {e}")
        return False
    finally:
        await conn.close() if conn else None

async def update_product_price(product_name: str, new_price: float) -> bool:
    """Mahsulot narxini yangilaydi."""
    conn = await connect_db()
    if not conn: return False
    try:
        result = await conn.execute("""
            UPDATE products
            SET price = $1
            WHERE name = $2;
        """, new_price, product_name)
        
        # 'UPDATE 1' yoki 'UPDATE 0' qaytaradi.
        return result == 'UPDATE 1'
    except Exception as e:
        logging.error(f"Mahsulot narxini yangilashda xato: {e}")
        return False
    finally:
        await conn.close() if conn else None

# --- IV. Hisob-kitob Mantig'i (SQL versiyasi) ---

async def calculate_agent_stock(agent_name: str) -> float:
    """Agentdagi jami mahsulot miqdorini (KG) hisoblaydi."""
    conn = await connect_db()
    if not conn: return 0.0
    try:
        # STOCK jadvalidagi quantity_kg yig'indisi
        total_stock = await conn.fetchval("""
            SELECT COALESCE(SUM(quantity_kg), 0)
            FROM stock
            WHERE agent_name = $1;
        """, agent_name)
        return float(total_stock)
    except Exception as e:
        logging.error(f"Agent stogini hisoblashda xato: {e}")
        return 0.0
    finally:
        await conn.close() if conn else None

async def calculate_agent_debt(agent_name: str) -> Tuple[float, float]:
    """Agentning jami qarzdorligi (musbat) va haqdorligi (manfiy) ni hisoblaydi."""
    conn = await connect_db()
    if not conn: return 0.0, 0.0
    
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
            return current_debt, 0.0 # Qarzdorlik, Haqdorlik (0)
        else:
            return 0.0, abs(current_debt) # Qarzdorlik (0), Haqdorlik
            
    except Exception as e:
        logging.error(f"Agent qarzini hisoblashda xato: {e}")
        return 0.0, 0.0
    finally:
        await conn.close() if conn else None

# --- V. Ma'lumot Kiritish Mantig'i (SQL versiyasi) ---

async def add_stock_transaction(agent_name: str, product_name: str, qty_kg: float, issue_price: float) -> bool:
    """Agentga tovar berish (yoki savdo qilish uchun o'tkazish) amaliyotini yozadi."""
    conn = await connect_db()
    if not conn: return False
    
    total_cost = qty_kg * issue_price
    
    try:
        await conn.execute("""
            INSERT INTO stock (agent_name, product_name, quantity_kg, issue_price, total_cost)
            VALUES ($1, $2, $3, $4, $5);
        """, agent_name, product_name, qty_kg, issue_price, total_cost)
        return True
    except Exception as e:
        logging.error(f"Stok tranzaksiyasini qo'shishda xato: {e}")
        return False
    finally:
        await conn.close() if conn else None
        
async def add_debt_payment(agent_name: str, amount: float, comment: str, is_payment: bool = True) -> bool:
    """Agent tomonidan pul to'lash (qarzni qoplash) yoki avans berish amaliyotini yozadi."""
    conn = await connect_db()
    if not conn: return False

    # To'lov (payment) uchun manfiy qiymat, Avans uchun musbat qiymat
    final_amount = -amount if is_payment else amount
    txn_type = "Qoplash" if is_payment else "Avans"
    txn_date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        await conn.execute("""
            INSERT INTO debt (agent_name, transaction_type, amount, txn_date, comment)
            VALUES ($1, $2, $3, $4, $5);
        """, agent_name, txn_type, final_amount, txn_date, comment)
        return True
    except Exception as e:
        logging.error(f"Qarz to'lovini/Avansni qo'shishda xato: {e}")
        return False
    finally:
        await conn.close() if conn else None

async def add_sales_transaction(agent_name: str, product_name: str, qty_kg: float, sale_price: float) -> bool:
    """Agentning savdo tranzaksiyasini yozadi (bu qarzga ta'sir qilmaydi, faqat hisobot uchun)."""
    conn = await connect_db()
    if not conn: return False

    total_amount = qty_kg * sale_price
    now = datetime.now()
    sale_date = now.strftime("%Y-%m-%d")
    sale_time = now.strftime("%H:%M:%S")

    try:
        await conn.execute("""
            INSERT INTO sales (agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
        """, agent_name, product_name, qty_kg, sale_price, total_amount, sale_date, sale_time)
        return True
    except Exception as e:
        logging.error(f"Savdo tranzaksiyasini qo'shishda xato: {e}")
        return False
    finally:
        await conn.close() if conn else None

# --- VI. KUNLIK SAVDO PIVOT HISOBOTI (Monospace) ---

async def get_daily_sales_pivot_report() -> Optional[str]:
    """
    Kunlik savdo ma'lumotlarini bazadan oladi va rasmdagi kabi
    Monospace formatda chiqaradi (MFY / Agent / Sana bo'yicha pivot).
    """
    conn = await connect_db()
    if not conn: return "⚠️ Ma'lumotlar bazasiga ulanib bo'lmadi."

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
        
        # 7. Ustunlarni rasmdagi tartibga keltirish
        date_cols = [col for col in pivot_df.columns if col not in ['MFY_Nomi', 'Agent_Ismi', 'Jami_Savdo']]
        date_cols.sort()
        
        final_cols = ['Jami_Savdo'] + date_cols
        pivot_df = pivot_df[final_cols]
        
        pivot_df = pivot_df.reset_index()

        # 8. Matnni Monospace formatida shakllantirish (Oldingi yechim kabi)
        
        col_widths = {
            'MFY_Nomi': pivot_df['MFY_Nomi'].str.len().max() or 10,
            'Agent_Ismi': pivot_df['Agent_Ismi'].str.len().max() or 15,
            'Jami_Savdo': 10 # Maksimal 10 belgi (misol: 1234.50 kg)
        }
        for col in date_cols:
            col_widths[col] = 7

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

        # --- Jami Yig'indi Qatori (Total Sum) - (Yangi) ---
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
    finally:
        await conn.close() if conn else None
