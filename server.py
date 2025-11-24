# server.py

# ==============================================================================
# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# ==============================================================================

import asyncio
import logging
from aiohttp import web # Web server yaratish uchun
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties  # YANGI: Aiogram 3.x uchun
from aiogram.types import Update, BotCommandScopeAllPrivateChats
from config import BOT_TOKEN, WEB_SERVER_HOST, WEB_SERVER_PORT, WEBHOOK_URL, WEBHOOK_PATH, ADMIN_IDS
import database
from admin_handlers import admin_router
from seller_handlers import seller_router

# Log darajasini o'rnatish
logging.basicConfig(level=logging.INFO)

# ==============================================================================
# II. BOT, DISPATCHER VA HANDLERLARNI O'RNATISH
# ==============================================================================

# YANGI SINTAKSIS: DefaultBotProperties orqali parse_mode='HTML' ni o'rnatamiz
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
    """Telegramdan kelgan yangi yangilanish (update) so'rovlariga ishlov berish."""
    # Agar so'rov bot tokeni bilan bir xil yo'l (path) bo'lmasa, rad etish
    if request.match_info.get('token') != BOT_TOKEN:
        return web.Response(status=403)
        
    data = await request.json()
    
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
    
    # 1. DB jadvallarini yaratish
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
            # types.BotCommand(command="admin_menu", description="Admin paneliga kirish"), # Agar mavjud bo'lsa yoqing
            types.BotCommand(command="cancel", description="Amaliyotni bekor qilish"),
        ],
        scope=types.BotCommandScopeAllPrivateChats()
    )

    # 4. Administratorga xabar berish
    for admin_id in ADMIN_IDS:
        try:
            # ID raqam ekanligiga ishonch hosil qilish
            admin_id = int(admin_id) 
            await bot.send_message(admin_id, "🚀 Bot Webhook rejimida ishga tushdi va Render.com da ulandi.")
        except Exception as e:
            logging.warning(f"Admin ID {admin_id} ga xabar yuborishda xato: {e}")


async def on_shutdown(app: web.Application):
    """Server to'xtaganda (bir marta) bajariladigan funksiya."""
    logging.warning('Server o\'chirilmoqda...')
    
    # Webhookni o'chirib qo'yish
    await bot.delete_webhook()
    
    # Bot sessiyasini yopish
    await bot.session.close()


def main():
    """
    Asosiy funksiya. Render/Gunicorn ishlatilganda, faqat aiohttp ilovasini qaytaradi.
    Bu, 'RuntimeError: Cannot run the event loop while another loop is running' xatosini oldini oladi.
    """
    
    # aiohttp ilovasini yaratish
    app = web.Application()

    # Serverni ishga tushirish/o'chirishda chaqiriladigan funksiyalarni ro'yxatdan o'tkazish
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Webhook manzilini belgilash (WEBHOOK_PATH = "/webhook/<token>")
    app.router.add_post(WEBHOOK_PATH, telegram_webhook_handler)

    # Ilovani qaytarish
    return app


if __name__ == '__main__':
    # Lokal test qilish uchun ishlatiladi (Renderda ishlamaydi)
    app = main()
    web.run_app(
        app,
        host=WEB_SERVER_HOST,
        port=WEB_SERVER_PORT
    )
