# keyboards.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- Umumiy Tugmalar ---
cancel_btn = InlineKeyboardButton(text="❌ Bekor Qilish", callback_data="cancel_op")


# ==============================================================================
# I. AGENT (SOTUVCHI) KLAVIATURASI (YANGILANDI)
# ==============================================================================

# Agent asosiy menusi (ReplyKeyboardMarkup)
seller_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🛍️ Savdo Kiritish"),
            KeyboardButton(text="💰 Balans & Statistika")
        ],
        [
            KeyboardButton(text="💰 To'lov Qabul Qilish") # YANGI: Agent to'lov qabul qilish uchun
        ],
        [
            KeyboardButton(text="🔝 Asosiy Menu") # Fayllarda boshqa menu kiritilmagani uchun /start buyrug'ini takrorlaydi
        ]
    ],
    resize_keyboard=True,
    selective=True
)

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
            KeyboardButton(text="🔝 Asosiy Menu") # /start ga qaytish
        ]
    ],
    resize_keyboard=True,
    selective=True
)

# Admin Sozlamalar menusi (InlineKeyboardMarkup)
admin_settings_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Agent qo'shish/o'chirish", callback_data="admin_agents"),
            InlineKeyboardButton(text="📦 Mahsulot qo'shish/o'chirish", callback_data="admin_products")
        ],
        [
            InlineKeyboardButton(text="📈 Stok Kiritish", callback_data="admin_add_stock"),
            InlineKeyboardButton(text="💸 Pul Harakati", callback_data="admin_add_debt")
        ]
    ]
)
