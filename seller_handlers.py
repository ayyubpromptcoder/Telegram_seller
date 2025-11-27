# seller_handlers.py fayli uchun tayyor kod

# ==============================================================================
# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# ==============================================================================

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database
import keyboards as kb
from config import ADMIN_IDS, DEFAULT_UNIT # ADMIN_IDS va DEFAULT_UNIT bu yerda mavjud bo'lishi kerak
import logging
from aiogram.types import ReplyKeyboardRemove

logging.basicConfig(level=logging.INFO)

seller_router = Router()

# ==============================================================================
# I. FSM (Holat Mashinasi)
# ==============================================================================

class SellState(StatesGroup):
    """Savdo kiritish uchun holatlar"""
    waiting_for_product = State()
    waiting_for_quantity = State()
    waiting_for_price = State()

class LoginState(StatesGroup):
    """Tizimga kirish holati"""
    waiting_for_password = State()

class DebtState(StatesGroup):
    """Qarzni qoplash (To'lov) holati"""
    waiting_for_payment_amount = State()
    waiting_for_payment_comment = State()
    
# ==============================================================================
# II. TIZIMGA KIRISH / ASOSIY MENU (YANGILANGAN)
# ==============================================================================

# Faqat ADMIN BO'LMAGAN foydalanuvchilar uchun ishlaydigan handler
# Bu routerda ishlaydi, shuning uchun ~F.from_user.id.in_(ADMIN_IDS) talab qilinmaydi,
# ammo xavfsizlik uchun qoldirilsa ham zarar qilmaydi.
@seller_router.message(CommandStart())
@seller_router.message(F.text == "🔝 Asosiy Menu")
async def cmd_start_seller(message: Message, state: FSMContext):
    """Botni ishga tushirish, Telegram ID orqali avtomatik login qilish."""
    # Agar Admin bo'lsa, bu handler ishlamaydi (Chunki Bot Dispatcherida Admin routeri oldin turishi kerak)
    await state.clear()
    
    # 1. Telegram ID orqali agentni topish
    agent_data = await database.get_agent_by_telegram_id(message.from_user.id)
    
    if agent_data:
        # Agent topildi (avtomatik login)
        await message.answer(
            f"Xush kelibsiz, **{agent_data['agent_name']}**! \nSizning MFY: **{agent_data['region_mfy']}**",
            reply_markup=kb.seller_main_kb,
            parse_mode="Markdown"
        )
    else:
        # Agent topilmadi (login paroli so'rash)
        await message.answer(
            "Xush kelibsiz! Botdan foydalanish uchun sizga **agent paroli** kerak.\n"
            "Parolingizni kiriting. (Bu sizning Telegram ID'ingizga bog'lanadi)",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(LoginState.waiting_for_password)

@seller_router.message(LoginState.waiting_for_password)
async def process_login_password(message: Message, state: FSMContext):
    """Parolni qabul qilish va agentni Telegram ID'ga bog'lash."""
    password = message.text.strip()
    
    # 1. Parol orqali agentni topish
    agent_data = await database.get_agent_by_password(password)
    
    if agent_data:
        # 2. Agentni Telegram ID bilan bog'lash
        success = await database.update_agent_telegram_id(agent_data['agent_name'], message.from_user.id)
        
        if success:
            await message.answer(
                f"✅ Tizimga kirish muvaffaqiyatli! **{agent_data['agent_name']}** \n"
                f"Sizning Telegram ID'ingiz saqlandi. Keyingi kirishlar avtomatik bo'ladi.",
                reply_markup=kb.seller_main_kb,
                parse_mode="Markdown"
            )
            await state.clear()
        else:
            await message.answer("❌ Login muvaffaqiyatsiz. Bu parol allaqachon boshqa Telegram ID'ga bog'langan bo'lishi mumkin. Admindan so'rang.")
    else:
        await message.answer("❌ Noto'g'ri parol. Qayta urinib ko'ring yoki /start bosing.")

# ==============================================================================
# III. BALANS/STATISTIKANI KO'RISH (YANGILANGAN - Batafsil Stok)
# ==============================================================================

@seller_router.message(F.text == "💰 Balans & Statistika")
async def show_seller_balance(message: Message):
    """Agentning stok va qarz holatini batafsil ko'rsatadi."""
    
    # 1. Loginni tekshirish (Telegram ID orqali)
    agent_data = await database.get_agent_by_telegram_id(message.from_user.id)
    if not agent_data:
        return await message.answer("Siz tizimga kirmagansiz yoki agent sifatida ro'yxatdan o'tmagansiz. /start")

    agent_name = agent_data['agent_name']
    
    # 2. Stok miqdorini hisoblash (List[Dict] qaytaradi)
    stock_data = await database.calculate_agent_stock(agent_name)
    
    # 3. Qarzni hisoblash
    debt, credit = await database.calculate_agent_debt(agent_name)

    report_parts = []
    total_stock_balance = sum(item['balance_qty'] for item in stock_data)

    # --- A. Qarz/Haqdorlik hisoboti ---
    report_parts.append(f"**💸 Pul Hisobi ({agent_name})**")
    if debt > 0:
        report_parts.append(f"**⚠️ Umumiy Qarzdorlik:** `{debt:,.0f} UZS`")
        report_parts.append("*(Bu: Olingan tovarlar narxi + Olingan Avanslar - Qilingan To'lovlar)*\n")
    elif credit > 0:
        report_parts.append(f"**✅ Siz Haqdor (Ortiqcha To'lov):** `{credit:,.0f} UZS`\n")
    else:
        report_parts.append("**Hisob-kitob holati:** Qarz mavjud emas.\n")
    
    report_parts.append("---")
    
    # --- B. Stok Hisoboti ---
    report_parts.append(f"**📦 Stok Hisobi**")
    report_parts.append(f"**Jami Qoldiq:** `{total_stock_balance:,.1f} {DEFAULT_UNIT}`\n")
    
    if stock_data:
        report_parts.append("```")
        report_parts.append("MAHSULOT NOMI       | QOLDIQ (KG)") # Eslatma: Tabulator o'rniga bo'shliqlar ishlatilgan
        report_parts.append("--------------------|------------")
        
        max_name_len = 18
        
        for item in stock_data:
            name = item['product_name']
            balance = item['balance_qty']
            
            display_name = name
            if len(name) > max_name_len:
                 display_name = name[:max_name_len-3] + "..."
                
            # Agar qoldiq 0 ga yaqin bo'lsa (0.1 dan kichik) ko'rsatmaslik
            # 0.1 dan kichik musbat va manfiy qoldiqlar yashiriladi (0 dan tashqari)
            if abs(balance) < 0.1 and balance != 0: 
                continue 
                
            # String formatlashda .ljust() bilan birga float formatlash uchun ehtiyotkor bo'lish kerak
            balance_str = f"{balance:,.1f}"
            
            # Kiritilgan kodda .rjust(12) olib tashlangan, bu to'g'ri. Endi faqat ljust ishlatamiz:
            report_parts.append(
                f"{display_name.ljust(max_name_len)} | {balance_str}"
            )
        
        report_parts.append("```")

    await message.answer("\n".join(report_parts), reply_markup=kb.seller_main_kb, parse_mode="Markdown")

# ==============================================================================
# IV. SAVDO KIRITISH - FSM JARAYONI
# ==============================================================================

@seller_router.message(F.text == "🛍️ Savdo Kiritish")
async def start_sell(message: Message, state: FSMContext):
    """Savdo kiritish jarayonini boshlaydi, mahsulotlarni ko'rsatadi."""
    
    agent_data = await database.get_agent_by_telegram_id(message.from_user.id)
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=product_buttons),
        parse_mode="Markdown"
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
        parse_mode="Markdown"
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
        parse_mode="Markdown"
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
            reply_markup=kb.seller_main_kb,
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Savdoni bazaga kiritishda xato yuz berdi. Iltimos, qayta urinib ko'ring.", reply_markup=kb.seller_main_kb)
        
    await state.clear()


# ==============================================================================
# V. TO'LOV QABUL QILISH - FSM JARAYONI (YANGI BO'LIM)
# ==============================================================================

@seller_router.message(F.text == "💰 To'lov Qabul Qilish")
async def start_debt_payment(message: Message, state: FSMContext):
    """To'lov qabul qilish jarayonini boshlaydi."""
    
    agent_data = await database.get_agent_by_telegram_id(message.from_user.id)
    if not agent_data:
        return await message.answer("Siz tizimga kirmagansiz. /start")

    await state.update_data(agent_name=agent_data['agent_name'])
    
    await message.answer(
        "Qabul qilingan **pul miqdorini** (so'mda) kiriting:\n"
        "*(Iltimos, faqat musbat butun raqam kiriting)*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
        parse_mode="Markdown"
    )
    await state.set_state(DebtState.waiting_for_payment_amount)

@seller_router.message(DebtState.waiting_for_payment_amount)
async def process_payment_amount(message: Message, state: FSMContext):
    """To'lov miqdorini qabul qilib, izohni so'raydi."""
    try:
        amount = int(message.text.strip())
        if amount <= 0: raise ValueError
    except ValueError:
        return await message.answer("Miqdor noto'g'ri kiritildi. Iltimos, musbat butun raqam kiriting (masalan: 1000000):")
    
    await state.update_data(payment_amount=amount)
    
    await message.answer(
        f"To'lov miqdori: **{amount:,.0f} UZS**.\n\n"
        f"**Izoh** yoki mijoz nomini kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
        parse_mode="Markdown"
    )
    await state.set_state(DebtState.waiting_for_payment_comment)

@seller_router.message(DebtState.waiting_for_payment_comment)
async def finish_debt_payment(message: Message, state: FSMContext):
    """Izohni qabul qilib, to'lovni bazaga kiritadi."""
    comment = message.text.strip()
    data = await state.get_data()
    
    agent_name = data['agent_name']
    amount = data['payment_amount']
    
    # To'lovni bazaga kiritish (is_payment=True bilan qoplash sifatida)
    success = await database.add_debt_payment(agent_name, amount, comment, is_payment=True)
    
    if success:
        await message.answer(
            "✅ **To'lov muvaffaqiyatli qabul qilindi!**\n\n"
            f"Agent: **{agent_name}**\n"
            f"Miqdor: **{amount:,.0f} UZS**\n"
            f"Izoh: **{comment}**",
            reply_markup=kb.seller_main_kb,
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ To'lovni bazaga kiritishda xato yuz berdi. Iltimos, qayta urinib ko'ring.", reply_markup=kb.seller_main_kb)
        
    await state.clear()


# ==============================================================================
# VI. BEKOR QILISH FUNKSIYASI (O'zgarmadi, lekin FSM holatlari ko'paydi)
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

# seller_handlers.py faylining eng oxirida
# Bu handler Adminlar uchun ishlamasligiga ishonch hosil qilish uchun, agar asosiy
# dispatcherda admin_router birinchi navbatda qo'yilmagan bo'lsa,
# bu yerda ham ~F.from_user.id.in_(ADMIN_IDS) filtrini ishlatish tavsiya etiladi.

@seller_router.message(~F.from_user.id.in_(ADMIN_IDS))
async def handle_all_other_messages(message: Message, state: FSMContext):
    """
    Agar foydalanuvchi FSM holatida bo'lmasa va yuqoridagi 
    handlerlarning hech biri ishlamasa, bu xabarga javob beradi.
    """
    current_state = await state.get_state()
    
    if current_state:
        # Agar FSM holatida bo'lsa, ammo noto'g'ri kiritma yuborgan bo'lsa
        await message.answer("⚠️ Noto'g'ri kiritma. Iltimos, kutilgan formatdagi ma'lumotni kiriting yoki /cancel bosing.")
    else:
        # Oddiy start/menyuga tushmagan bo'lsa
        await message.answer("Sizni tushunmadim. Iltimos, /start buyrug'ini bosing yoki menudan tanlang.", 
                             reply_markup=kb.seller_main_kb)
