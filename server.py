# server.py
# Bu fayl botni webhook rejimida ishga tushirish uchun mo'ljallangan

# ==============================================================================
# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# ==============================================================================

import asyncio
import logging
from aiohttp import web 
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update, BotCommandScopeAllPrivateChats, BotCommandScopeChat

# Loyiha fayllaridan importlar
from config import BOT_TOKEN, WEB_SERVER_HOST, WEB_SERVER_PORT, WEBHOOK_URL, WEBHOOK_PATH, ADMIN_IDS
import database
from admin_handlers import admin_router
from seller_handlers import seller_router

# Log darajasini o'rnatish
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# II. BOT, DISPATCHER VA ROUTERLARNI O'RNATISH
# ==============================================================================

# Botni global parse_mode (Markdown yoki HTML) bilan yaratish
# Biz HTML ni tanlaymiz, chunki MarkdownV2 bilan tez-tez muammolar bo'ladi
default_properties = DefaultBotProperties(parse_mode="HTML") 
bot = Bot(token=BOT_TOKEN, default=default_properties)

dp = Dispatcher()

# Routerlarni ulash: ADMIN routeri birinchi turishi kerak
dp.include_router(admin_router)
dp.include_router(seller_router)


# ==============================================================================
# III. WEBHOOK HANDLER (HTTP SO'ROVGA ISHLOV BERISH)
# ==============================================================================

async def telegram_webhook_handler(request: web.Request):
    """
    Telegramdan kelgan yangilanish (update) so'rovlariga ishlov berish.
    Webhook URL'ini tekshirish xavfsizlik uchun muhim.
    """
    
    # Xavfsizlikni tekshirish: URL manzilini taqqoslash
    if request.path != WEBHOOK_PATH:
        logging.warning(f"Ruxsatsiz kirish urinishi: {request.path}")
        return web.Response(status=403) # Forbidden
        
    try:
        data = await request.json()
    except Exception as e:
        logging.error(f"JSON ma'lumotlarini o'qishda xato: {e}")
        return web.Response(status=400) 

    # Telegram yangilanishini Deserializatsiya qilish
    update = Update.model_validate(data, context={"bot": bot})
    
    # Dispatcher orqali yangilanishni qayta ishlash (asinxron)
    await dp.feed_update(bot, update)
    
    # Telegramga muvaffaqiyatli qabul qilinganligi haqida xabar berish
    return web.Response(status=200)

# ==============================================================================
# IV. SERVERNI ISHGA TUSHIRISH/O'CHIRISH FUNKSIYALARI
# ==============================================================================

async def setup_commands(bot: Bot):
    """Bot buyruqlarini Telegramga o'rnatadi."""
    
    # Umumiy buyruqlar (Barcha shaxsiy chatlar uchun)
    general_commands = [
        types.BotCommand(command="start", description="Tizimga kirish / Asosiy menu"),
        types.BotCommand(command="cancel", description="Amaliyotni bekor qilish"),
    ]
    await bot.set_my_commands(general_commands, scope=BotCommandScopeAllPrivateChats())
    
    # Admin uchun maxsus buyruqlar
    if ADMIN_IDS:
        admin_commands = [
            types.BotCommand(command="start", description="Admin Boshqaruv Paneli"),
            types.BotCommand(command="mahsulot", description="Mahsulotlar Bo'limi"),
            types.BotCommand(command="sotuvchi", description="Sotuvchilar Bo'limi"),
            types.BotCommand(command="cancel", description="Amaliyotni bekor qilish"),
        ]
        
        # Har bir admin uchun buyruqlarni o'rnatish
        for admin_id in ADMIN_IDS:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id)
            )

async def on_startup(app: web.Application):
    """Server ishga tushganda (bir marta) bajariladigan funksiya."""
    logging.info("🚀 Server ishga tushirilmoqda...")
    
    # 1. DB jadvallarini yaratish/tekshirish
    db_ready = await database.create_tables()
    if not db_ready:
        logging.critical("❌ Ma'lumotlar bazasi tayyor emas. Ishlash to'xtatiladi.")
        raise RuntimeError("Database initialization failed.")

    # 2. Webhook manzilini Telegramga o'rnatish
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"🔗 Webhook o'rnatildi: {WEBHOOK_URL}")
    
    # 3. Buyruqlar ro'yxatini Telegramga o'rnatish 
    await setup_commands(bot)
    logging.info("⚙️ Buyruqlar ro'yxati yangilandi.")

    # 4. Administratorga xabar berish
    if ADMIN_IDS:
        try:
            # Faqat birinchi admin_id ga yuborish
            await bot.send_message(ADMIN_IDS[0], "✅ Bot ishga tushdi va Webhook o'rnatildi.")
        except Exception as e:
            logging.warning(f"Adminlarga xabar yuborishda xato yuz berdi: {e}")


# server.py faylida
# ... (Import qismini o'zgartirmang, 'import database' qolishi kerak)

async def on_shutdown(app: web.Application):
    """Server to'xtaganda (bir marta) bajariladigan funksiya."""
    logging.warning('🛑 Server o\'chirilmoqda...')
    
    # 1. Webhookni o'chirib qo'yish
    await bot.delete_webhook()
    
    # 2. DB ulanish havzasini yopish
    # database.py dan DB_POOL global o'zgaruvchisini chaqirish
    if database.DB_POOL:
        await database.DB_POOL.close()
        logging.info("PostgreSQL ulanish havzasi yopildi.")

    # 3. Bot sessiyasini yopish
    await bot.session.close()
    logging.info("Bot sessiyasi yopildi va Webhook o'chirildi.")
    
# ...


# ==============================================================================
# V. ASOSIY ILOVA YARATUVCHISI
# ==============================================================================

async def create_app():
    """
    aiohttp Application obyektini yaratadi. 
    Bu funksiya Gunicorn kabi WSGI/ASGI serverlar tomonidan chaqiriladi.
    """
    
    # aiohttp ilovasini yaratish
    app = web.Application()

    # Serverni ishga tushirish/o'chirish funksiyalarini ro'yxatdan o'tkazish
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Webhook manzilini belgilash
    app.router.add_post(WEBHOOK_PATH, telegram_webhook_handler)

    # Ilovani qaytarish
    return app


if __name__ == '__main__':
    # Lokal test qilish uchun muhit
    try:
        app = asyncio.run(create_app()) 
        web.run_app(
            app,
            host=WEB_SERVER_HOST,
            port=WEB_SERVER_PORT
        )
    except Exception as e:
        logging.critical(f"Kritik xato: Bot ishga tushmadi. {e}")
