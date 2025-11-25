# server.py

# ==============================================================================
# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# ... (O'zgarmaydi)
# ==============================================================================
import asyncio
import logging
from aiohttp import web 
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update, BotCommandScopeAllPrivateChats
from config import BOT_TOKEN, WEB_SERVER_HOST, WEB_SERVER_PORT, WEBHOOK_URL, WEBHOOK_PATH, ADMIN_IDS
import database
from admin_handlers import admin_router
from seller_handlers import seller_router

logging.basicConfig(level=logging.INFO)

# ==============================================================================
# II. BOT, DISPATCHER VA HANDLERLARNI O'RNATISH
# ... (O'zgarmaydi)
# ==============================================================================
default_properties = DefaultBotProperties(parse_mode="HTML")
bot = Bot(token=BOT_TOKEN, default=default_properties)
dp = Dispatcher()
dp.include_router(admin_router)
dp.include_router(seller_router)


# ==============================================================================
# III. WEBHOOK HANDLER (O'zgarmaydi)
# ==============================================================================
async def telegram_webhook_handler(request: web.Request):
    # ... (kod o'zgarmaydi)
    if request.match_info.get('token') != BOT_TOKEN:
        return web.Response(status=403)
        
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return web.Response(status=200)

# ==============================================================================
# IV. SERVERNI ISHGA TUSHIRISH FUNKSIYALARI
# ==============================================================================

# on_startup va on_shutdown funksiyalari avvalgi holatida qoladi
async def on_startup(app: web.Application):
    """Server ishga tushganda (bir marta) bajariladigan funksiya."""
    logging.info("Server ishga tushirilmoqda...")
    
    # 1. DB jadvallarini yaratish (Async funksiya)
    db_ready = await database.create_tables()
    if not db_ready:
        logging.error("Ma'lumotlar bazasi tayyor emas. Ishlash to'xtatiladi.")
        raise RuntimeError("Database initialization failed.")

    # 2. Webhook manzilini Telegramga o'rnatish (Async funksiya)
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")
    
    # 3. Buyruqlar ro'yxatini Telegramga o'rnatish (Async funksiya)
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Tizimga kirish / Asosiy menu"),
            types.BotCommand(command="cancel", description="Amaliyotni bekor qilish"),
        ],
        scope=types.BotCommandScopeAllPrivateChats()
    )

    # 4. Administratorga xabar berish (Async funksiya)
    for admin_id in ADMIN_IDS:
        try:
            admin_id = int(admin_id) 
            await bot.send_message(admin_id, "🚀 Bot Webhook rejimida ishga tushdi va Render.com da ulandi.")
        except Exception as e:
            logging.warning(f"Admin ID {admin_id} ga xabar yuborishda xato: {e}")


async def on_shutdown(app: web.Application):
    """Server to'xtaganda (bir marta) bajariladigan funksiya."""
    logging.warning('Server o\'chirilmoqda...')
    
    await bot.delete_webhook()
    await bot.session.close()


# ASOSIY TUZATISH: main funksiyasini async ga aylantirish
async def main():
    """
    Asosiy funksiya. aiohttp.GunicornWebWorker talabiga ko'ra,
    bu funksiya async bo'lishi va Application obyektini qaytarishi kerak.
    """
    
    # aiohttp ilovasini yaratish
    app = web.Application()

    # Serverni ishga tushirish/o'chirishda chaqiriladigan funksiyalarni ro'yxatdan o'tkazish
    # Bu funksiyalar (on_startup, on_shutdown) app ichida chaqiriladi.
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Webhook manzilini belgilash (WEBHOOK_PATH = "/webhook/<token>")
    # Eslatma: request.match_info.get('token') ni ishlatish uchun pathda {token} bo'lishi kerak.
    # Agar sizning WEBHOOK_PATH'ingiz /webhook/{BOT_TOKEN} kabi bo'lsa, bu to'g'ri ishlaydi.
    app.router.add_post(WEBHOOK_PATH, telegram_webhook_handler)

    # Ilovani qaytarish
    return app


if __name__ == '__main__':
    # Lokal test qilish uchun ishlatiladi (Renderda ishlamaydi)
    app = asyncio.run(main())
    web.run_app(
        app,
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT
    )
