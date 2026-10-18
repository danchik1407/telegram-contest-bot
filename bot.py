import asyncio
import logging
import os
import signal
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError

from config import BOT_TOKEN, ADMIN_IDS, CONTEST_DURATION, UPDATE_INTERVAL
from services.contest import ContestManager
from handlers.commands import register_command_handlers
from handlers.messages import register_message_handlers
from handlers.economy import register_economy_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

bot_instance = None
dp_instance = None
contest_manager_instance = None

async def handle_health(request):
    return web.Response(text="Bot is running!")

async def start_http_server():
    port = int(os.environ.get('PORT', 10000))
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"HTTP-сервер запущен на порту {port}")

async def main():
    global bot_instance, dp_instance, contest_manager_instance

    bot_instance = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp_instance = Dispatcher()

    contest_manager_instance = ContestManager(
        duration=CONTEST_DURATION,
        update_interval=UPDATE_INTERVAL
    )

    register_command_handlers(dp_instance, contest_manager_instance, ADMIN_IDS)
    register_message_handlers(dp_instance, contest_manager_instance, bot_instance)
    register_economy_handlers(dp_instance, bot_instance)

    await start_http_server()

    max_retries = 5
    retry_count = 0

    while retry_count < max_retries:
        try:
            logger.info("Запускаем polling...")
            await dp_instance.start_polling(bot_instance)
            break
        except TelegramConflictError as e:
            retry_count += 1
            logger.warning(f"Конфликт polling ({retry_count}/{max_retries}): {e}")
            if retry_count >= max_retries:
                logger.error("Превышено количество попыток подключения.")
                break
            await asyncio.sleep(5)
            logger.info("Повторная попытка через 5 секунд...")
        except Exception as e:
            logger.error(f"Критическая ошибка polling: {e}")
            break

    if bot_instance:
        await bot_instance.session.close()
        logger.info("Сессия бота закрыта")

def shutdown_handler(signum, frame):
    logger.info("Получен сигнал завершения. Корректно завершаем работу...")
    if bot_instance:
        asyncio.create_task(bot_instance.session.close())

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (KeyboardInterrupt)")