from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database
import keyboards as kb
from config import ADMIN_IDS, DEFAULT_UNIT

seller_router = Router()

# ==============================================================================
# I. FSM (Holat Mashinasi) - Savdo kiritish
# ==============================================================================

class SellState(StatesGroup):
    """Savdo kiritish uchun holatlar"""
    waiting_for_product = State()
    waiting_for_quantity = State()
    waiting_for_price = State()
    
# ==============================================================================
# II. TIZIMGA KIRISH / ASOSIY MENU
# ==============================================================================

# Faqat ADMIN BO'LMAGAN foydalanuvchilar uchun ishlaydigan handler
@seller_router.message(CommandStart(), ~F.from_user.id.in_(ADMIN_IDS))
@seller_router.message(F.text == "🔝 Asosiy Menu", ~F.from_user.id.in_(ADMIN_IDS))
async def cmd_start_seller(message: Message, state: FSMContext):
    """Botni ishga tushirish va agentga kirish menyusini ko'rsatish."""
    await state.clear()
    
    # database.get_agent_by_password hozirda str(message.from_user.id) ni parol sifatida ishlatadi
    agent_name = (await database.get_agent_by_password(str(message.from_user.id)))
    
    # Eslatma: Adminlar bu yerga tashqi filtr (~F.from_user.id.in_(ADMIN_IDS)) tufayli kelmaydi
    if agent_name:
        # Agentlar uchun asosiy menu
        await message.answer(
            f"Xush kelibsiz, **{agent_name['agent_name']}**! \nSizning MFY: **{agent_name['region_mfy']}**",
            reply_markup=kb.seller_main_kb
        )
    else:
        # Ro'yxatdan o'tmagan foydalanuvchilar
        await message.answer(
            "Xush kelibsiz! Botdan foydalanish uchun sizga agent paroli kerak.\n"
            "Parolingizni kiriting. (Bu sizning Telegram ID'ingizga bog'lanadi)"
        )
        pass

# ==============================================================================
# III. BALANS/STATISTIKANI KO'RISH
# ==============================================================================

@seller_router.message(F.text == "💰 Balans & Statistika")
async def show_seller_balance(message: Message):
    """Agentning stok va qarz holatini ko'rsatadi."""
    
    # ID dan foydalanib agent nomini topish
    agent_data = await database.get_agent_by_password(str(message.from_user.id))
    if not agent_data:
        return await message.answer("Siz tizimga kirmagansiz yoki agent sifatida ro'yxatdan o'tmagansiz. /start")

    agent_name = agent_data['agent_name']
    
    # Stok miqdorini hisoblash
    stock_kg = await database.calculate_agent_stock(agent_name)
    
    # Qarzni hisoblash
    debt, credit = await database.calculate_agent_debt(agent_name)

    report_text = f"**📊 Agent Balans Hisoboti ({agent_name})**\n\n"
    
    report_text += f"**Jami Stok Qoldig'i (KG):** `{stock_kg:.1f} {DEFAULT_UNIT}`\n\n"
    
    if debt > 0:
        report_text += f"**⚠️ Umumiy Qarzdorlik:** `{debt:,.2f} UZS`\n"
        report_text += "(Bu: Olingan tovarlar narxi + Olingan Avanslar - Qilingan To'lovlar)\n"
    elif credit > 0:
        report_text += f"**✅ Siz Haqdor (Ortiqcha To'lov):** `{credit:,.2f} UZS`\n"
    else:
        report_text += "**Hisob-kitob holati:** Qarz mavjud emas."
        
    await message.answer(report_text, reply_markup=kb.seller_main_kb)

# ==============================================================================
# IV. SAVDO KIRITISH - FSM JARAYONI
# ==============================================================================

@seller_router.message(F.text == "🛍️ Savdo Kiritish")
async def start_sell(message: Message, state: FSMContext):
    """Savdo kiritish jarayonini boshlaydi, mahsulotlarni ko'rsatadi."""
    
    agent_data = await database.get_agent_by_password(str(message.from_user.id))
    if not agent_data:
        return await message.answer("Siz tizimga kirmagansiz. /start")

    products = await database.get_all_products()
    if not products:
        return await message.answer("Mahsulotlar ro'yxati bazada mavjud emas. Admindan yuklashni so'rang.")
        
    await state.update_data(agent_name=agent_data['agent_name'])
    
    # Mahsulot tugmalarini yaratish
    product_buttons = [
        [InlineKeyboardButton(text=f"{p['name']} ({p['price']:,.0f} UZS)", callback_data=f"sel_{p['name']}")]
        for p in products
    ]
    product_buttons.append([kb.cancel_btn])
    
    await message.answer(
        "Savdo qilgan **mahsulotni** tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=product_buttons)
    )
    await state.set_state(SellState.waiting_for_product)

# --- 4.1 Mahsulot Tanlandi ---
@seller_router.callback_query(SellState.waiting_for_product, F.data.startswith("sel_"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    product_name = callback.data.split('_')[1]
    
    await state.update_data(product_name=product_name)
    
    await callback.message.edit_text(
        f"Mahsulot: **{product_name}**\n\n"
        f"Sotilgan **miqdorni** ({DEFAULT_UNIT}) kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]])
    )
    await state.set_state(SellState.waiting_for_quantity)
    await callback.answer()

# --- 4.2 Miqdor Kiritildi ---
@seller_router.message(SellState.waiting_for_quantity)
async def select_price(message: Message, state: FSMContext):
    try:
        qty_kg = float(message.text.replace(',', '.').strip())
        if qty_kg <= 0: raise ValueError
    except ValueError:
        return await message.answer("Miqdor noto'g'ri kiritildi. Iltimos, musbat raqam kiriting (masalan: 10.5):")
        
    data = await state.get_data()
    product_name = data['product_name']
    
    # Mahsulotning standart narxini olish
    product_info = await database.get_product_info(product_name)
    default_price = product_info['price'] if product_info else 0
    
    await state.update_data(qty_kg=qty_kg)
    
    await message.answer(
        f"Mahsulot: **{product_name}** ({qty_kg:.1f} {DEFAULT_UNIT})\n\n"
        f"Sotilgan **narxni** (1 {DEFAULT_UNIT} uchun, so'mda) kiriting.\n"
        f"*(Standart narx: {default_price:,.0f} UZS)*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]])
    )
    await state.set_state(SellState.waiting_for_price)

# --- 4.3 Narx Kiritildi (Yakuniy) ---
@seller_router.message(SellState.waiting_for_price)
async def finish_sell(message: Message, state: FSMContext):
    try:
        sale_price = float(message.text.replace(',', '.').strip())
        if sale_price <= 0: raise ValueError
    except ValueError:
        return await message.answer("Narx noto'g'ri kiritildi. Iltimos, musbat raqam kiriting (masalan: 7500):")
    
    data = await state.get_data()
    agent_name = data['agent_name']
    product_name = data['product_name']
    qty_kg = data['qty_kg']
    
    # Savdoni bazaga kiritish
    success = await database.add_sales_transaction(agent_name, product_name, qty_kg, sale_price)
    
    if success:
        total_amount = qty_kg * sale_price
        await message.answer(
            "✅ **Savdo muvaffaqiyatli kiritildi!**\n\n"
            f"Tovar: **{product_name}**\n"
            f"Miqdor: **{qty_kg:.1f} {DEFAULT_UNIT}**\n"
            f"Narx: **{sale_price:,.0f} UZS**\n"
            f"Jami: **{total_amount:,.0f} UZS**",
            reply_markup=kb.seller_main_kb
        )
    else:
        await message.answer("❌ Savdoni bazaga kiritishda xato yuz berdi. Iltimos, qayta urinib ko'ring.", reply_markup=kb.seller_main_kb)
        
    await state.clear()
    
# ==============================================================================
# V. BEKOR QILISH FUNKSIYASI
# ==============================================================================

@seller_router.callback_query(F.data == "cancel_op")
@seller_router.message(Command("cancel"))
async def cancel_handler(callback_or_message: [CallbackQuery, Message], state: FSMContext):
    """Joriy FSM jarayonini bekor qiladi."""
    current_state = await state.get_state()
    if current_state is None:
        if isinstance(callback_or_message, CallbackQuery):
            await callback_or_message.answer("Bekor qilinadigan jarayon yo'q.")
        return

    await state.clear()
    
    text = "❌ Amaliyot bekor qilindi."
    
    if isinstance(callback_or_message, CallbackQuery):
        await callback_or_message.message.edit_text(text, reply_markup=None)
        await callback_or_message.message.answer("Asosiy menu:", reply_markup=kb.seller_main_kb)
        await callback_or_message.answer()
    else:
        await callback_or_message.answer(text, reply_markup=kb.seller_main_kb)
