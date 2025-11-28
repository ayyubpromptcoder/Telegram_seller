# ==============================================================================
# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# ==============================================================================

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
# TelegramBadRequest xatoligini qo'shish (callback.message.edit_text ishlatilganda kerak bo'lishi mumkin)
from aiogram.exceptions import TelegramBadRequest 
import database 
import keyboards as kb 
from config import ADMIN_IDS, DEFAULT_UNIT 
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Router yaratish
seller_router = Router()

# ==============================================================================
# II. FSM (Holat Mashinasi)
# ==============================================================================

class SellState(StatesGroup):
    """Savdo kiritish uchun holatlar"""
    waiting_for_product = State()
    waiting_for_quantity = State()
    waiting_for_price = State()

class LoginState(StatesGroup):
    """Tizimga kirish holati"""
    waiting_for_password = State()

class PaymentState(StatesGroup):
    """To'lov (Agentning qarzini qoplashi) holati"""
    waiting_for_payment_amount = State()
    waiting_for_payment_comment = State()
    
# ==============================================================================
# III. TIZIMGA KIRISH / ASOSIY MENU
# ==============================================================================

# Faqat Admin bo'lmagan foydalanuvchilar uchun
@seller_router.message(CommandStart())
@seller_router.message(F.text == "🔝 Asosiy Menu")
async def cmd_start_seller(message: Message, state: FSMContext):
    """Botni ishga tushirish, Telegram ID orqali avtomatik login qilish."""
    await state.clear()
    
    # 1. Telegram ID orqali agentni topish
    agent_data = await database.get_agent_by_telegram_id(message.from_user.id)
    
    if agent_data:
        # Agent topildi (avtomatik login)
        await message.answer(
            f"Xush kelibsiz, **{agent_data['agent_name']}**! \nSizning MFY: **{agent_data.get('region_mfy', '—')}**",
            reply_markup=kb.seller_main_kb,
            parse_mode="Markdown"
        )
    else:
        # Agent topilmadi (login paroli so'rash)
        # Agar bu Admin bo'lsa, o'zini tanitishga majbur qilmaslik uchun tekshiruv kiritildi:
        if message.from_user.id in ADMIN_IDS:
             return await message.answer("Siz Admin paneldasiz. /admin_menu buyrug'ini bosing.", reply_markup=ReplyKeyboardRemove())

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

## 💰 Balans va Statistika
---

# ==============================================================================
# IV. BALANS/STATISTIKANI KO'RISH (Batafsil Stok)
# ==============================================================================

@seller_router.message(F.text == "💰 Balans & Statistika")
async def show_seller_balance(message: Message):
    """Agentning stok va qarz holatini batafsil ko'rsatadi."""
    
    # 1. Loginni tekshirish
    agent_data = await database.get_agent_by_telegram_id(message.from_user.id)
    if not agent_data:
        return await message.answer("Siz tizimga kirmagansiz yoki agent sifatida ro'yxatdan o'tmagansiz. /start")

    agent_name = agent_data['agent_name']
    
    # 2. Stok miqdorini hisoblash
    # Ushbu funksiya uzoq ishlashi mumkin, shuning uchun yuklanmoqda xabarini berish maqsadga muvofiq
    sent_message = await message.answer("Hisob-kitoblar tayyorlanmoqda, iltimos kuting...")

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
        # Faqat 0 ga yaqin bo'lmagan qoldiqlarni filtrlash
        display_stock = [item for item in stock_data if abs(item['balance_qty']) >= 0.1 or item['balance_qty'] == 0]

        if display_stock:
            report_parts.append("```")
            report_parts.append("MAHSULOT NOMI            | QOLDIQ (KG)")
            report_parts.append("------------------------|------------")
            
            max_name_len = 24 # Kod blokida to'g'ri ko'rinish uchun sozlandi (yuqorida 22 edi)
            
            for item in display_stock:
                name = item['product_name']
                balance = item['balance_qty']
                
                display_name = name
                if len(name) > max_name_len:
                    display_name = name[:max_name_len-3] + "..."
                    
                balance_str = f"{balance:,.1f}".rjust(12) # Raqamlarni o'ng tomonga tekislash
                
                report_parts.append(
                    f"{display_name.ljust(max_name_len)} | {balance_str}"
                )
        
            report_parts.append("```")
        else:
            report_parts.append("*Bazaga kiritilgan qoldiqli mahsulotlar yo'q.*")


    try:
        # Oldingi "yuklanmoqda" xabarini tahrirlash
        await sent_message.edit_text(
            "\n".join(report_parts), 
            reply_markup=kb.seller_main_kb, 
            parse_mode="Markdown"
        )
    except TelegramBadRequest as e:
        # Xabar tahrirlanmasa (masalan, o'zgartirilmagan bo'lsa)
        logging.info(f"Balans xabari tahrirlanmadi: {e}")
        # Shunchaki yuborib qo'yish
        await message.answer("\n".join(report_parts), reply_markup=kb.seller_main_kb, parse_mode="Markdown")

## 🛍️ Savdo Kiritish
---

# ==============================================================================
# V. SAVDO KIRITISH - FSM JARAYONI
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
        [InlineKeyboardButton(text=f"{p['name']} ({p.get('price', 0):,.0f} UZS)", callback_data=f"sel_{p['name']}")]
        for p in products
    ]
    product_buttons.append([kb.cancel_btn])
    
    await message.answer(
        "Savdo qilgan **mahsulotni** tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=product_buttons),
        parse_mode="Markdown"
    )
    await state.set_state(SellState.waiting_for_product)

# --- 5.1 Mahsulot Tanlandi ---
@seller_router.callback_query(SellState.waiting_for_product, F.data.startswith("sel_"))
async def select_quantity(callback: CallbackQuery, state: FSMContext):
    product_name = callback.data.split('_')[1]
    
    await state.update_data(product_name=product_name)
    
    try:
        await callback.message.edit_text(
            f"Mahsulot: **{product_name}**\n\n"
            f"Sotilgan **miqdorni** ({DEFAULT_UNIT}) kiriting:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
            parse_mode="Markdown"
        )
    except TelegramBadRequest:
        # Xabar tahrirlanmasa (masalan, oldingi xabar yangilangan bo'lsa), yangi xabar yuborish
        await callback.message.answer(
            f"Mahsulot: **{product_name}**\n\nSotilgan **miqdorni** ({DEFAULT_UNIT}) kiriting:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
            parse_mode="Markdown"
        )
        
    await state.set_state(SellState.waiting_for_quantity)
    await callback.answer()

# --- 5.2 Miqdor Kiritildi ---
@seller_router.message(SellState.waiting_for_quantity)
async def select_price(message: Message, state: FSMContext):
    try:
        # Nuqta va vergulni qabul qilish uchun .replace(',', '.') ishlatilgan, yaxshi!
        qty_kg = float(message.text.replace(',', '.').strip()) 
        if qty_kg <= 0: raise ValueError
    except ValueError:
        return await message.answer("Miqdor noto'g'ri kiritildi. Iltimos, **musbat raqam** kiriting (masalan: 10.5):")
        
    data = await state.get_data()
    product_name = data['product_name']
    
    # Mahsulotning standart narxini olish
    product_info = await database.get_product_info(product_name)
    default_price = product_info.get('price', 0) if product_info else 0
    
    await state.update_data(qty_kg=qty_kg)
    
    await message.answer(
        f"Mahsulot: **{product_name}** ({qty_kg:.1f} {DEFAULT_UNIT})\n\n"
        f"Sotilgan **narxni** (1 {DEFAULT_UNIT} uchun, so'mda) kiriting.\n"
        f"*(Standart narx: {default_price:,.0f} UZS)*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
        parse_mode="Markdown"
    )
    await state.set_state(SellState.waiting_for_price)

# --- 5.3 Narx Kiritildi (Yakuniy) ---
@seller_router.message(SellState.waiting_for_price)
async def finish_sell(message: Message, state: FSMContext):
    try:
        sale_price = float(message.text.replace(',', '.').strip())
        if sale_price <= 0: raise ValueError
    except ValueError:
        return await message.answer("Narx noto'g'ri kiritildi. Iltimos, **musbat raqam** kiriting (masalan: 7500):")
    
    data = await state.get_data()
    agent_name = data['agent_name']
    product_name = data['product_name']
    qty_kg = data['qty_kg']
    
    # Savdoni bazaga kiritish
    success = await database.add_sales_transaction(agent_name, product_name, qty_kg, sale_price)
    
    await state.clear() # Muhim: Clear oldinroq bo'lishi kerak.
    
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
        

## 💸 To'lov Kiritish
---

# ==============================================================================
# VI. TO'LOV QABUL QILISH - FSM JARAYONI
# ==============================================================================

@seller_router.message(F.text == "💸 To'lov Kiritish")
async def start_debt_payment(message: Message, state: FSMContext):
    """To'lov kiritish jarayonini boshlaydi."""
    
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
    await state.set_state(PaymentState.waiting_for_payment_amount)

@seller_router.message(PaymentState.waiting_for_payment_amount)
async def process_payment_amount(message: Message, state: FSMContext):
    """To'lov miqdorini qabul qilib, izohni so'raydi."""
    try:
        # To'lov pul bo'lgani uchun int(message.text.strip()) o'rinli.
        amount = int(message.text.strip()) 
        if amount <= 0: raise ValueError
    except ValueError:
        return await message.answer("Miqdor noto'g'ri kiritildi. Iltimos, **musbat butun raqam** kiriting (masalan: 1000000):")
        
    await state.update_data(payment_amount=amount)
    
    await message.answer(
        f"To'lov miqdori: **{amount:,.0f} UZS**.\n\n"
        f"**Izoh** yoki mijoz nomini kiriting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[kb.cancel_btn]]),
        parse_mode="Markdown"
    )
    await state.set_state(PaymentState.waiting_for_payment_comment)

@seller_router.message(PaymentState.waiting_for_payment_comment)
async def finish_debt_payment(message: Message, state: FSMContext):
    """Izohni qabul qilib, to'lovni bazaga kiritadi."""
    comment = message.text.strip()
    data = await state.get_data()
    
    agent_name = data['agent_name']
    amount = data['payment_amount']
    
    # To'lovni bazaga kiritish (is_payment=True bilan qoplash sifatida)
    success = await database.add_debt_payment(agent_name, amount, comment, is_payment=True)
    
    await state.clear() # Muhim: Clear!

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
        

## ❌ Bekor Qilish & Fallback
---

# ==============================================================================
# VII. BEKOR QILISH FUNKSIYASI
# ==============================================================================

@seller_router.callback_query(F.data == "cancel_op")
@seller_router.message(Command("cancel"))
async def cancel_handler(callback_or_message: [CallbackQuery, Message], state: FSMContext):
    """Joriy FSM jarayonini bekor qiladi."""
    current_state = await state.get_state()
    
    if current_state is None:
        if isinstance(callback_or_message, CallbackQuery):
            # Inline tugma bosilganda jarayon bo'lmasa, xabar qoldirish
            await callback_or_message.answer("Bekor qilinadigan jarayon yo'q.")
        elif isinstance(callback_or_message, Message):
            await callback_or_message.answer("Bekor qilinadigan jarayon yo'q.", reply_markup=kb.seller_main_kb)
        return

    await state.clear()
    
    text = "❌ Amaliyot bekor qilindi."
    
    if isinstance(callback_or_message, CallbackQuery):
        # CallbackQuery bo'lsa, xabarni tahrirlash va yangi xabar yuborish
        try:
            await callback_or_message.message.edit_text(text, reply_markup=None)
        except TelegramBadRequest:
            await callback_or_message.message.answer(text, reply_markup=kb.seller_main_kb)
        
        await callback_or_message.message.answer("Asosiy menu:", reply_markup=kb.seller_main_kb)
        await callback_or_message.answer()
    else:
        # Message bo'lsa, oddiy javob yuborish
        await callback_or_message.answer(text, reply_markup=kb.seller_main_kb)

# ==============================================================================
# VIII. BOSHQA XABARLARNI QAYTA ISHLASH (FALLBACK)
# ==============================================================================

# Faqat Admin BO'LMAGAN foydalanuvchilardan kelgan xabarlarga javob beradi
# Eslatma: Bu yerda ~F.from_user.id.in_(ADMIN_IDS) filtri bor, shuning uchun bu agentlarga tegishli.
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
