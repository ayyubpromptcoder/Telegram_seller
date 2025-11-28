# ==============================================================================
# server.py (Long Polling)
# Bu fayl botni uzoq so'rov (Long Polling) rejimida ishga tushirish uchun mo'ljallangan
# ==============================================================================

# I. KERAKLI KUTUBXONALARNI IMPORT QILISH
# aiohttp dan foydalanilmaydi
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
# Update (webhook uchun) o'rniga faqat kerakli scope'lar import qilinadi
from aiogram.types import BotCommandScopeAllPrivateChats, BotCommandScopeChat

# Loyiha fayllaridan importlar
# Webhook/Server sozlamalari endi kerak emas, faqat bot token va admin ID'lar
from config import BOT_TOKEN, ADMIN_IDS
import database
from admin_handlers import admin_router
from seller_handlers import seller_router

# Log darajasini o'rnatish
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==============================================================================
# II. BOT, DISPATCHER VA ROUTERLARNI O'RNATISH
# ==============================================================================

# Botni global parse_mode (HTML) bilan yaratish
default_properties = DefaultBotProperties(parse_mode="HTML") 
bot = Bot(token=BOT_TOKEN, default=default_properties)

dp = Dispatcher()

# Routerlarni ulash
dp.include_router(admin_router)
dp.include_router(seller_router)


# ==============================================================================
# III. BOT BUYRUQLARINI O'RNATISH
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
    logging.info("⚙️ Buyruqlar ro'yxati yangilandi.")


# ==============================================================================
# IV. ASOSIY LONG POLLING FUNKSIYASI
# ==============================================================================

async def main():
    """Botni Long Polling rejimida ishga tushiradi va barcha zaruriy amallarni bajaradi."""
    logging.info("🚀 Bot ishga tushirilmoqda (Long Polling)...")

    # 1. DB jadvallarini yaratish/tekshirish
    db_ready = await database.create_tables()
    if not db_ready:
        logging.critical("❌ Ma'lumotlar bazasi tayyor emas. Ishlash to'xtatiladi.")
        return 

    # 2. Oldingi Webhookni o'chirib qo'yish (agar mavjud bo'lsa)
    # drop_pending_updates=True botni ishga tushirishdan oldin turib qolgan xabarlarni o'chiradi
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("🔗 Webhook o'chirildi va kutilayotgan yangilanishlar tashlab yuborildi.")

    # 3. Buyruqlar ro'yxatini Telegramga o'rnatish
    await setup_commands(bot)
    
    # 4. Administratorga xabar berish
    if ADMIN_IDS:
        try:
            await bot.send_message(ADMIN_IDS[0], "✅ Bot Long Polling rejimida ishga tushdi.")
        except Exception as e:
            logging.warning(f"Adminlarga xabar yuborishda xato yuz berdi: {e}")

    # 5. Long Pollingni boshlash
    try:
        await dp.start_polling(bot)
    finally:
        # 6. Bot to'xtaganda (ctrl+c yoki xatolik) DB havzasini yopish
        if database.DB_POOL:
            await database.DB_POOL.close()
            logging.info("PostgreSQL ulanish havzasi yopildi.")
        
        # 7. Bot sessiyasini yopish
        await bot.session.close()
        logging.warning("🛑 Bot to'xtatildi.")


if __name__ == '__main__':
    # Lokal test qilish uchun muhit
    try:
        # Asosiy asinxron funksiyani ishga tushirish
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.warning("Dastur foydalanuvchi tomonidan to'xtatildi (KeyboardInterrupt).")
    except Exception as e:
        logging.critical(f"Kritik xato: Bot ishga tushmadi. {e}")
