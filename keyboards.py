# ==============================================================================
# keyboards.py
# ==============================================================================

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

# --- Umumiy Tugmalar ---
# Operatsiyani bekor qilish uchun (FSM holatidan chiqishda foydalaniladi)
cancel_btn = InlineKeyboardButton(text="❌ Bekor Qilish", callback_data="cancel_op")
back_btn = InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_menu")


# ==============================================================================
# I. AGENT (SOTUVCHI) KLAVIATURASI
# ==============================================================================

# Agent asosiy menusi (ReplyKeyboardMarkup)
seller_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🛍️ Savdo Kiritish"),
            KeyboardButton(text="💰 Balans & Statistika")
        ],
        [
            KeyboardButton(text="💸 To'lov Kiritish") # Agent pul to'laganini kiritadi
        ],
        [
            # /start buyrug'ini bevosita chaqiradi (Asosiy menyuga qaytish uchun)
            KeyboardButton(text="🔝 /start") 
        ]
    ],
    resize_keyboard=True,
    selective=True
)

def get_products_kb(products: List[Dict]) -> InlineKeyboardMarkup:
    """
    Mahsulotlar ro'yxatini InlineKeyboardMarkup sifatida qaytaradi.
    Eslatma: seller_handlers.py da bu Inline tugmalar bevosita yaratilgan, ammo bu funksiya dinamik KB uchun namuna bo'ladi.
    """
    buttons = []
    for product in products:
        # Callback data uchun prod_ prefiksi ishlatildi (Agar foydalanilmasa, seller_handlers.py dagi sel_ bilan almashtirilishi kerak)
        product_name = product.get('name', 'Nomsiz')
        product_price = product.get('price', 0)
        
        callback_data = f"prod_{product_name}"[:64] 
        # Tugmada narxni ko'rsatish
        buttons.append([InlineKeyboardButton(text=f"{product_name} ({product_price:,.0f} UZS)", callback_data=callback_data)])
    
    buttons.append([cancel_btn])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==============================================================================
# II. ADMIN KLAVIATURASI
# ==============================================================================

# Admin asosiy menusi (ReplyKeyboardMarkup)
admin_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Hisobotlar"),
            KeyboardButton(text="⚙️ Sozlamalar")
        ],
        [
            # /start buyrug'ini bevosita chaqiradi (Asosiy menyuga qaytish uchun)
            KeyboardButton(text="🔝 /start") 
        ]
    ],
    resize_keyboard=True,
    selective=True
)

# Admin Sozlamalar menusi (InlineKeyboardMarkup) - Kiritish/Yangilash operatsiyalari
admin_settings_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Agent qo'shish", callback_data="admin_add_agent"),
            InlineKeyboardButton(text="📦 Mahsulot qo'shish", callback_data="admin_add_product")
        ],
        [
            # Agentga tovar berish (Stok)
            InlineKeyboardButton(text="📈 Stok Kiritish", callback_data="admin_add_stock"), 
            # Agentga pul berish/Agentdan pul olish (Avans/Qoplash)
            InlineKeyboardButton(text="💸 Pul Harakati", callback_data="admin_add_debt") 
        ],
        [
            back_btn # Asosiy menyuga qaytish
        ]
    ]
)

# Admin Hisobotlar menusi (InlineKeyboardMarkup)
admin_reports_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Kunlik Savdo Pivoti", callback_data="report_daily_pivot")],
        [InlineKeyboardButton(text="👥 Agentlar Balansi", callback_data="report_agent_balances")],
        [back_btn]
    ]
)
