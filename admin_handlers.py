# admin_handlers.py

# ==============================================================================
# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# ==============================================================================

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import ADMIN_IDS, DEFAULT_UNIT
import database # Neon DB bilan ishlash uchun

# Admin routerini yaratish
admin_router = Router()

# ==============================================================================
# II. FSM HOLATLARI (Finite State Machine)
# ==============================================================================
# Adminning ketma-ket ma'lumot kiritish jarayonlarini boshqarish uchun

class AdminStates(StatesGroup):
    # --- Mahsulot boshqaruvi ---
    NEW_PRODUCT_NAME = State()
    NEW_PRODUCT_PRICE = State()
    SET_NEW_PRICE = State()

    # --- Sotuvchi qo'shish ---
    ADD_AGENT_REGION = State()
    ADD_AGENT_NAME = State()
    ADD_AGENT_PHONE = State()
    ADD_AGENT_PASSWORD = State()

    # --- Savdo kiritish (Ehtiyoj bo'lsa) ---
    # ...


# ==============================================================================
# III. YORDAMCHI FUNKSIYALAR
# ==============================================================================

def is_admin(user_id: int) -> bool:
    """Foydalanuvchi Admin_IDs ro'yxatida mavjudligini tekshiradi."""
    return user_id in ADMIN_IDS

def get_agent_management_buttons(agent_name: str) -> types.InlineKeyboardMarkup:
    """Agent ma'lumotlari menu buttonlarini yaratadi."""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔑 Sotuvchi Paroli", callback_data=f"agent_pass:{agent_name}")],
            [types.InlineKeyboardButton(text=f"📦 Sotuvchidagi Mahsulot ({DEFAULT_UNIT})", callback_data=f"agent_stock:{agent_name}")],
            [types.InlineKeyboardButton(text="💸 Sotuvchi Qarzdorligi", callback_data=f"agent_debt:{agent_name}")]
        ]
    )

# ==============================================================================
# IV. ADMIN ASOSIY BUYRUQLARI VA MENYULARI
# ==============================================================================

@admin_router.message(Command("start"))
@admin_router.message(Command("admin_menu"))
async def handle_start(message: types.Message):
    """Adminlar uchun start buyrug'i va asosiy menu."""
    if not is_admin(message.from_user.id):
        # Admin bo'lmagan foydalanuvchi seller_handlers.py ga yo'naltiriladi
        return

    # Admin asosiy menyu (Reply Keyboard)
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="/mahsulot"), types.KeyboardButton(text="/sotuvchi")],
            [types.KeyboardButton(text="📊 Kunlik Savdo Hisoboti")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Siz Admin panelidasiz. Boshqaruv menyusini tanlang:", reply_markup=keyboard)


@admin_router.message(Command("mahsulot"))
async def handle_mahsulot_menu(message: types.Message):
    """'Mahsulot' buyrug'iga ishlov berish."""
    if not is_admin(message.from_user.id): return
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Yangi Mahsulot Kiritish", callback_data="add_new_product")],
            [types.InlineKeyboardButton(text="🛒 Mahsulotlar Ro'yxati", callback_data="list_products")]
        ]
    )
    await message.answer("Mahsulotlar bo'limi:", reply_markup=keyboard)


@admin_router.message(Command("sotuvchi"))
async def handle_sotuvchi_menu(message: types.Message):
    """'Sotuvchi' buyrug'iga ishlov berish."""
    if not is_admin(message.from_user.id): return
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📦 Sotuvchilardagi Mahsulotlar", callback_data="agent_stock_summary")],
            [types.InlineKeyboardButton(text="👥 Sotuvchilar", callback_data="list_all_agents_menu")],
            [types.InlineKeyboardButton(text="➕ Yangi Sotuvchi Qo'shish", callback_data="add_new_agent_start")]
        ]
    )
    await message.answer("Sotuvchilar bo'limi:", reply_markup=keyboard)

@admin_router.message(F.text == "📊 Kunlik Savdo Hisoboti")
async def handle_daily_sales_report(message: types.Message):
    """Kunlik savdo hisobotini bazadan olib, monospace formatda chiqaradi."""
    if not is_admin(message.from_user.id): return
    
    await message.answer("Hisobot tayyorlanmoqda, iltimos kuting...")
    
    # database.py dagi funksiyani chaqirish
    report_text = await database.get_daily_sales_pivot_report()
    
    await message.answer(report_text, parse_mode="Markdown")

# ==============================================================================
# V. MAHSULOT BO'LIMI MANTIG'I
# ==============================================================================

# --- 5.1 Yangi mahsulot kiritish (FSM) ---

@admin_router.callback_query(F.data == "add_new_product")
async def start_add_product(callback: types.CallbackQuery, state: FSMContext):
    """Yangi mahsulot nomini so'rashni boshlaydi."""
    await callback.message.edit_text("Yangi mahsulot nomini kiriting:")
    await state.set_state(AdminStates.NEW_PRODUCT_NAME)
    await callback.answer()

@admin_router.message(AdminStates.NEW_PRODUCT_NAME)
async def process_product_name(message: types.Message, state: FSMContext):
    """Mahsulot nomini qabul qilib, narxini so'raydi."""
    await state.update_data(product_name=message.text.strip())
    await message.answer("Mahsulot narxini (faqat raqamlarda) kiriting:")
    await state.set_state(AdminStates.NEW_PRODUCT_PRICE)

@admin_router.message(AdminStates.NEW_PRODUCT_PRICE)
async def process_product_price(message: types.Message, state: FSMContext):
    """Mahsulot narxini qabul qilib, bazaga kiritadi."""
    try:
        price = float(message.text.strip())
        data = await state.get_data()
        product_name = data['product_name']
        
        # Baza: Yangi mahsulot kiritish
        if await database.add_new_product(product_name, price):
            await message.answer(
                f"✅ Mahsulot **{product_name}** ({price:,.0f} so'm) bazaga kiritildi.", 
                parse_mode="Markdown", 
                reply_markup=get_mahsulot_keyboard() # get_mahsulot_keyboard() ni funksiya sifatida yaratish kerak
            )
        else:
            await message.answer("❌ Mahsulotni bazaga kiritishda xato yuz berdi. (Nom takrorlangan bo'lishi mumkin)")
            
        await state.clear()
    except ValueError:
        await message.answer("Narx noto'g'ri kiritildi. Iltimos, faqat raqamlarda kiriting:")

# --- 5.2 Mahsulotlar ro'yxati va narxni yangilash ---

@admin_router.callback_query(F.data == "list_products")
async def list_products(callback: types.CallbackQuery):
    """Barcha mahsulotlarni buttonlar sifatida ko'rsatadi."""
    products = await database.get_all_products()
    if not products:
        await callback.message.edit_text("Hozirda mahsulotlar ro'yxati bo'sh.")
        await callback.answer()
        return

    buttons = []
    for p in products:
        # Callback data: product_info:{MahsulotNomi}
        buttons.append([types.InlineKeyboardButton(text=f"{p['name']} ({p['price']:,.0f} so'm)", callback_data=f"product_info:{p['name']}")])
    
    await callback.message.edit_text("Mahsulotni tanlang:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@admin_router.callback_query(F.data.startswith("product_info:"))
async def show_product_info(callback: types.CallbackQuery, state: FSMContext):
    """Tanlangan mahsulot narxini ko'rsatadi va yangilash imkonini beradi."""
    product_name = callback.data.split(":")[1]
    product = await database.get_product_info(product_name)
    
    if product:
        # FSM da mahsulot nomini saqlaymiz
        await state.update_data(product_to_update=product_name)
        
        text = (f"**Mahsulot:** {product['name']}\n"
                f"**Hozirgi Narxi:** {product['price']:,.0f} so'm / {DEFAULT_UNIT}")
        
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🆕 Yangi Narx Belgilash", callback_data="set_new_price_start")]
            ]
        )
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await callback.message.answer("Mahsulot topilmadi.")
    await callback.answer()

@admin_router.callback_query(F.data == "set_new_price_start")
async def start_set_new_price(callback: types.CallbackQuery, state: FSMContext):
    """Mahsulotning yangi narxini kiritish jarayonini boshlaydi."""
    data = await state.get_data()
    product_name = data.get('product_to_update')
    
    if not product_name:
        await callback.message.answer("⚠️ Avval mahsulotni tanlang.")
        await callback.answer()
        return
    
    await callback.message.edit_text(f"**{product_name}** uchun yangi narxni (faqat raqamlarda) kiriting:", parse_mode="Markdown")
    await state.set_state(AdminStates.SET_NEW_PRICE)
    await callback.answer()

@admin_router.message(AdminStates.SET_NEW_PRICE)
async def process_set_new_price(message: types.Message, state: FSMContext):
    """Kiritilgan yangi narxni bazaga yozadi."""
    try:
        new_price = float(message.text.strip())
        data = await state.get_data()
        product_name = data['product_to_update']
        
        # Baza: Narxni yangilash
        if await database.update_product_price(product_name, new_price):
            await message.answer(
                f"✅ Mahsulot **{product_name}**ning yangi narxi **{new_price:,.0f}** so'm etib belgilandi.\n\n"
                f"*(Eslatma: Oldin olingan tovarlar eski narxida qoladi)*", 
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Narxni yangilashda xato yuz berdi.")
        
        await state.clear()
        # Qaytish menyusi
        await message.answer("Mahsulotlar menyusiga qaytdingiz.", reply_markup=get_mahsulot_keyboard())
        
    except ValueError:
        await message.answer("Narx noto'g'ri kiritildi. Iltimos, faqat raqamlarda kiriting:")

# ==============================================================================
# VI. SOTUVCHI BO'LIMI MANTIG'I
# ==============================================================================

# --- 6.1 Yangi sotuvchi qo'shish (FSM) ---

@admin_router.callback_query(F.data == "add_new_agent_start")
async def start_add_agent(callback: types.CallbackQuery, state: FSMContext):
    """Agentning MFY/Region nomini so'rashni boshlaydi."""
    await callback.message.edit_text("Agentning **MFY/Region** nomini kiriting:")
    await state.set_state(AdminStates.ADD_AGENT_REGION)
    await callback.answer()

@admin_router.message(AdminStates.ADD_AGENT_REGION)
async def process_agent_region(message: types.Message, state: FSMContext):
    """MFYni qabul qilib, Agent Ismini so'raydi."""
    await state.update_data(region=message.text.strip())
    await message.answer("Agentning **Ismi va Familiyasini** kiriting (masalan: Alisher Bobojonov):")
    await state.set_state(AdminStates.ADD_AGENT_NAME)

@admin_router.message(AdminStates.ADD_AGENT_NAME)
async def process_agent_name(message: types.Message, state: FSMContext):
    """Agent Ismini qabul qilib, Telefon raqamini so'raydi."""
    await state.update_data(name=message.text.strip())
    await message.answer("Agentning **Telefon raqamini** kiriting (masalan: 991234567):")
    await state.set_state(AdminStates.ADD_AGENT_PHONE)

@admin_router.message(AdminStates.ADD_AGENT_PHONE)
async def process_agent_phone(message: types.Message, state: FSMContext):
    """Telefon raqamini qabul qilib, Parolni so'raydi."""
    await state.update_data(phone=message.text.strip())
    await message.answer("Agent uchun **maxfiy parolni** kiriting (Botga kirish uchun):")
    await state.set_state(AdminStates.ADD_AGENT_PASSWORD)

@admin_router.message(AdminStates.ADD_AGENT_PASSWORD)
async def process_agent_password(message: types.Message, state: FSMContext):
    """Parolni qabul qilib, Agentni bazaga kiritadi."""
    data = await state.get_data()
    
    region = data['region']
    name = data['name']
    phone = data['phone']
    password = message.text.strip()
    
    # Baza: Yangi agent kiritish
    if await database.add_new_agent(region, name, phone, password):
        await message.answer(
            f"✅ Yangi Agent bazaga kiritildi:\n"
            f"**Ism:** {name}\n"
            f"**MFY:** {region}\n"
            f"**Parol:** `{password}`",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Agentni bazaga kiritishda xato yuz berdi. (Agent nomi takrorlangan bo'lishi mumkin)")
        
    await state.clear()
    await message.answer("Sotuvchilar menyusiga qaytishingiz mumkin.", reply_markup=get_sotuvchi_keyboard())

# --- 6.2 Sotuvchilar ro'yxati va boshqaruvi menyusi ---

@admin_router.callback_query(F.data == "list_all_agents_menu")
async def list_all_agents_menu(callback: types.CallbackQuery):
    """Sotuvchilar ro'yxatini ko'rish usullari menyusi."""
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="👥 Barcha Sotuvchilar (Alifbo)", callback_data="list_all_agents_alpha")],
            [types.InlineKeyboardButton(text="🏠 Sotuvchilar MFY bo'yicha", callback_data="list_agents_by_mfy")],
            [types.InlineKeyboardButton(text="🔑 Sotuvchilar Parollari", callback_data="list_agent_passwords")]
        ]
    )
    await callback.message.edit_text("Sotuvchilar ro'yxati:", reply_markup=keyboard)
    await callback.answer()

# 6.2.1 Barcha Sotuvchilar (Alifbo tartibi)
@admin_router.callback_query(F.data == "list_all_agents_alpha")
async def list_all_agents_alpha(callback: types.CallbackQuery):
    """Barcha agentlarni MFY va Ism bo'yicha tartiblab chiqaradi."""
    agents = await database.get_all_agents()
    if not agents:
        await callback.message.answer("Hozirda sotuvchilar ro'yxati bo'sh.")
        await callback.answer()
        return
    
    buttons = []
    for agent in agents:
        buttons.append([types.InlineKeyboardButton(text=f"{agent['agent_name']} ({agent['region_mfy']})", callback_data=f"agent_details:{agent['agent_name']}")])
        
    await callback.message.edit_text("Agentni tanlang (MFY / Ism bo'yicha tartiblangan):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

# 6.2.2 Sotuvchilar MFY bo'yicha
@admin_router.callback_query(F.data == "list_agents_by_mfy")
async def list_agents_by_mfy(callback: types.CallbackQuery):
    """Barcha mavjud MFYlarni buttonlar sifatida ko'rsatadi."""
    agents = await database.get_all_agents()
    if not agents:
        await callback.message.answer("Hozirda sotuvchilar ro'yxati bo'sh.")
        await callback.answer()
        return
        
    # MFY ro'yxatini olish (takrorlanmas va tartiblangan)
    mfy_list = sorted(list(set(a['region_mfy'] for a in agents)))
    
    buttons = []
    for mfy in mfy_list:
        buttons.append([types.InlineKeyboardButton(text=mfy, callback_data=f"mfy_select:{mfy}")])
        
    await callback.message.edit_text("MFYni tanlang:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@admin_router.callback_query(F.data.startswith("mfy_select:"))
async def list_agents_in_mfy(callback: types.CallbackQuery):
    """Tanlangan MFYdagi agentlarni chiqaradi."""
    mfy_name = callback.data.split(":")[1]
    agents = await database.get_all_agents()
    
    mfy_agents = [a for a in agents if a['region_mfy'] == mfy_name]
    
    buttons = []
    for agent in mfy_agents:
        # Callback data: agent_details:{AgentNomi}
        buttons.append([types.InlineKeyboardButton(text=agent['agent_name'], callback_data=f"agent_details:{agent['agent_name']}")])
        
    await callback.message.edit_text(f"**{mfy_name}** MFY agentlari:", parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


# --- 6.3 Agent ma'lumotlari (Stok, Qarz, Parol) ---

@admin_router.callback_query(F.data.startswith("agent_details:"))
async def show_agent_details(callback: types.CallbackQuery):
    """Agent ma'lumotlarini ko'rish uchun menyuni ochadi."""
    agent_name = callback.data.split(":")[1]
    
    await callback.message.edit_text(
        f"**{agent_name}** agenti:", 
        parse_mode="Markdown", 
        reply_markup=get_agent_management_buttons(agent_name)
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("agent_pass:"))
async def show_agent_password(callback: types.CallbackQuery):
    """Agentning maxfiy parolini alert sifatida chiqaradi."""
    agent_name = callback.data.split(":")[1]
    agent = await database.get_agent_info(agent_name)
    
    if agent:
        text = f"Agent: {agent_name}\nParol: {agent['password']}"
    else:
        text = "Agent topilmadi."
        
    await callback.answer(text, show_alert=True)
    
@admin_router.callback_query(F.data.startswith("agent_stock:"))
async def show_agent_stock(callback: types.CallbackQuery):
    """Agentdagi jami mahsulot miqdorini chiqaradi."""
    agent_name = callback.data.split(":")[1]
    stock_qty = await database.calculate_agent_stock(agent_name)
    
    text = f"**{agent_name}**da jami **{stock_qty:,.1f} {DEFAULT_UNIT}** mahsulot mavjud."
    await callback.answer(text, show_alert=True)

@admin_router.callback_query(F.data.startswith("agent_debt:"))
async def show_agent_debt(callback: types.CallbackQuery):
    """Agentning qarzdorlik/haqdorligini chiqaradi."""
    agent_name = callback.data.split(":")[1]
    debt, credit = await database.calculate_agent_debt(agent_name)
    
    if debt > 0:
        text = f"**{agent_name}**ning jami qarzi: **{debt:,.0f} so'm**."
    elif credit > 0:
        text = f"**{agent_name}**da haqdorlik: **{credit:,.0f} so'm**."
    else:
        text = f"**{agent_name}**da qarzdorlik yo'q."
        
    await callback.answer(text, show_alert=True)
    
# 6.3.1 Sotuvchilar Parollari Ro'yxati (Monospace)

@admin_router.callback_query(F.data == "list_agent_passwords")
async def list_agent_passwords(callback: types.CallbackQuery):
    """Agent parollarini Monospace formatda ko'rsatadi."""
    agents = await database.get_all_agents()
    if not agents:
        await callback.message.answer("Hozirda sotuvchilar ro'yxati bo'sh.")
        await callback.answer()
        return
        
    # Monospace format uchun matnni yig'ish
    max_len = max(len(a['agent_name']) for a in agents) if agents else 15
    
    text = "🔑 **Agentlar Parollari Ro'yxati:**\n\n"
    text += "```\n"
    text += "AGENT NOMI".ljust(max_len) + " | PAROL\n"
    text += "-" * (max_len + 8) + "\n"
    
    for agent in agents:
        text += f"{agent['agent_name'].ljust(max_len)} | {agent['password']}\n"
    text += "```"

    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()
    
# --- 6.4 Sotuvchilardagi Mahsulotlar Ro'yxati (Agentlar kesimida) ---

@admin_router.callback_query(F.data == "agent_stock_summary")
async def list_all_agent_stocks(callback: types.CallbackQuery):
    """Barcha agentlar ro'yxatini chiqarib, ulardagi stokni ko'rish imkonini beradi."""
    agents = await database.get_all_agents()
    if not agents:
        await callback.message.edit_text("Hozirda sotuvchilar ro'yxati bo'sh.")
        return

    buttons = []
    for agent in agents:
        # agent_details funksiyasi orqali stok, qarz ko'riladi
        buttons.append([types.InlineKeyboardButton(text=f"{agent['agent_name']} ({agent['region_mfy']})", callback_data=f"agent_details:{agent['agent_name']}")])
        
    await callback.message.edit_text("Mahsulot qoldig'ini ko'rish uchun Agentni tanlang:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


# Funksiyani to'liq ishlashi uchun kerakli bo'lgan alohida button funksiyalarini oxirida qo'shamiz

def get_mahsulot_keyboard() -> types.InlineKeyboardMarkup:
    """Mahsulotlar bo'limi uchun klaviatura"""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Yangi Mahsulot Kiritish", callback_data="add_new_product")],
            [types.InlineKeyboardButton(text="🛒 Mahsulotlar Ro'yxati", callback_data="list_products")]
        ]
    )

def get_sotuvchi_keyboard() -> types.InlineKeyboardMarkup:
    """Sotuvchilar bo'limi uchun klaviatura"""
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📦 Sotuvchilardagi Mahsulotlar", callback_data="agent_stock_summary")],
            [types.InlineKeyboardButton(text="👥 Sotuvchilar", callback_data="list_all_agents_menu")],
            [types.InlineKeyboardButton(text="➕ Yangi Sotuvchi Qo'shish", callback_data="add_new_agent_start")]
        ]
    )
