import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS, CONTEST_DURATION, UPDATE_INTERVAL
from services.contest import ContestService
from handlers.commands import register_command_handlers
from handlers.messages import register_message_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# ─── Создаём бота и диспетчер ───
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

contest_service = ContestService(
    duration=CONTEST_DURATION,
    update_interval=UPDATE_INTERVAL
)

register_command_handlers(dp, contest_service, ADMIN_IDS)
register_message_handlers(dp, contest_service, bot)


# ─── HTTP-сервер для Render и UptimeRobot ───
async def handle_health(request):
    """Эту страницу будет проверять UptimeRobot."""
    return web.Response(text="Bot is running! ")


async def start_http_server():
    """Запускаем мини-веб-сервер на порту 10000 (требование Render)."""
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
    logging.info("HTTP-сервер запущен на порту 10000")


# ─── Главная функция ───
async def main():
    # Запускаем HTTP-сервер в фоне
    asyncio.create_task(start_http_server())

    # Запускаем бота
    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())