# keyboards.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

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
            # /start buyrug'ini bevosita chaqiradi
            KeyboardButton(text="🔝 /start") 
        ]
    ],
    resize_keyboard=True,
    selective=True
)

# Savdo va to'lov kiritishda miqdorni so'rashdan oldin mahsulotni tanlash uchun (Dynamic KB kerak, shunchaki namuna)
def get_products_kb(products: list[dict]) -> InlineKeyboardMarkup:
    """Mahsulotlar ro'yxatini InlineKeyboardMarkup sifatida qaytaradi."""
    buttons = []
    for product in products:
        # product_key_1 nomi bilan callback_data yaratiladi
        callback_data = f"prod_{product['name']}"[:64] # Max uzunligi 64
        buttons.append([InlineKeyboardButton(text=product['name'], callback_data=callback_data)])
    
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
            # /start buyrug'ini bevosita chaqiradi
            KeyboardButton(text="🔝 /start") 
        ]
    ],
    resize_keyboard=True,
    selective=True
)

# Admin Sozlamalar menusi (InlineKeyboardMarkup)
admin_settings_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Agent qo'shish", callback_data="admin_add_agent"),
            InlineKeyboardButton(text="📦 Mahsulot qo'shish", callback_data="admin_add_product")
        ],
        [
            InlineKeyboardButton(text="📈 Stok Kiritish", callback_data="admin_add_stock"),
            InlineKeyboardButton(text="💸 Pul Harakati", callback_data="admin_add_debt")
        ],
        [
            back_btn # Asosiy menyuga qaytish uchun (yoki shunchaki cancel_btn)
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
