# server.py

# ==============================================================================
# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# ==============================================================================

import asyncio
import logging
from aiohttp import web 
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Update, BotCommandScopeAllPrivateChats

# 'config.py', 'database.py', 'admin_handlers', 'seller_handlers' fayllaridan import qilinadi
from config import BOT_TOKEN, WEB_SERVER_HOST, WEB_SERVER_PORT, WEBHOOK_URL, WEBHOOK_PATH, ADMIN_IDS
import database
from admin_handlers import admin_router
from seller_handlers import seller_router

# Log darajasini o'rnatish
logging.basicConfig(level=logging.INFO)

# ==============================================================================
# II. BOT, DISPATCHER VA HANDLERLARNI O'RNATISH
# ==============================================================================

# DefaultBotProperties orqali HTML parse_mode ni o'rnatamiz
default_properties = DefaultBotProperties(parse_mode="HTML")

# Bot obyektini yangi sintaksisda yaratamiz
bot = Bot(token=BOT_TOKEN, default=default_properties)

dp = Dispatcher()

# Routerlarni ulash
dp.include_router(admin_router)
dp.include_router(seller_router)


# ==============================================================================
# III. WEBHOOK HANDLER (HTTP SO'ROVGA ISHLOV BERISH)
# ==============================================================================

async def telegram_webhook_handler(request: web.Request):
    """
    Telegramdan kelgan yangi yangilanish (update) so'rovlariga ishlov berish.
    URL manzilini tekshirishni WEBHOOK_PATH bilan solishtirish orqali amalga oshiradi 
    (403 Forbidden xatosini tuzatish uchun).
    """
    
    # Ruxsatsiz kirishning oldini olish uchun URL manzilini tekshirish
    if request.path != WEBHOOK_PATH:
        logging.warning(f"Ruxsatsiz kirish urinishi: {request.path}")
        return web.Response(status=403)
        
    try:
        # JSON ma'lumotlarini o'qish
        data = await request.json()
    except Exception as e:
        logging.error(f"JSON ma'lumotlarini o'qishda xato: {e}")
        return web.Response(status=400) # Noto'g'ri formatdagi so'rov

    # Telegram yangilanishini (update) Deserializatsiya qilish (JSON -> Update obyekt)
    update = Update.model_validate(data, context={"bot": bot})
    
    # Dispatcher orqali yangilanishni qayta ishlash
    await dp.feed_update(bot, update)
    
    # Telegramga muvaffaqiyatli qabul qilinganligi haqida xabar berish
    return web.Response(status=200)

# ==============================================================================
# IV. SERVERNI ISHGA TUSHIRISH FUNKSIYALARI
# ==============================================================================

async def on_startup(app: web.Application):
    """Server ishga tushganda (bir marta) bajariladigan funksiya."""
    logging.info("Server ishga tushirilmoqda...")
    
    # 1. DB jadvallarini yaratish/tekshirish
    db_ready = await database.create_tables()
    if not db_ready:
        logging.error("Ma'lumotlar bazasi tayyor emas. Ishlash to'xtatiladi.")
        raise RuntimeError("Database initialization failed.")

    # 2. Webhook manzilini Telegramga o'rnatish
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook o'rnatildi: {WEBHOOK_URL}")
    
    # 3. Buyruqlar ro'yxatini Telegramga o'rnatish 
    await bot.set_my_commands(
        [
            types.BotCommand(command="start", description="Tizimga kirish / Asosiy menu"),
            types.BotCommand(command="cancel", description="Amaliyotni bekor qilish"),
        ],
        scope=types.BotCommandScopeAllPrivateChats()
    )

    # 4. Administratorga xabar berish (Agar admin /start bosmagan bo'lsa, Warning chiqadi)

async def on_shutdown(app: web.Application):
    """Server to'xtaganda (bir marta) bajariladigan funksiya."""
    logging.warning('Server o\'chirilmoqda...')
    # Webhookni o'chirib qo'yish va bot sessiyasini yopish
    await bot.delete_webhook()
    await bot.session.close()


# ASOSIY FUNKSIYA: Gunicorn/aiohttp talabiga ko'ra async funksiya
async def main():
    """
    Asosiy funksiya. Gunicorn (aiohttp.GunicornWebWorker) talabiga ko'ra,
    bu funksiya async bo'lishi va Application obyektini qaytarishi kerak.
    """
    
    # aiohttp ilovasini yaratish
    app = web.Application()

    # Serverni ishga tushirish/o'chirish funksiyalarini ro'yxatdan o'tkazish
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Webhook manzilini belgilash
    app.router.add_post(WEBHOOK_PATH, telegram_webhook_handler)

    # Ilovani qaytarish (Gunicorn chaqiradi)
    return app


if __name__ == '__main__':
    # Lokal test qilish uchun kerak. Render.com da bu qism ishlamaydi.
    # Sinxron muhitda asinxron main() ni chaqirish
    app = asyncio.run(main()) 
    web.run_app(
        app,
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT
    )
