from aiogram import Router
from aiogram.types import Message, ChatPermissions
from aiogram.filters import Command
from aiogram.enums import ParseMode

from services.contest import ContestService
from utils.formatters import format_time_left
from utils.emoji import TROPHY, DIAMOND, FIRE, ROCKET, CROWN, GIFT, PARTY, STAR, CLOCK, SPARKLES

router = Router()


def register_command_handlers(dp, contest_service: ContestService, admin_ids: list):
    @dp.message(Command("start_contest"))
    async def cmd_start(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор может запустить конкурс.")
            return

        if contest_service.is_active:
            await message.answer("⚠️ Конкурс уже идёт!")
            return

        duration = contest_service.duration
        parts = message.text.split()
        if len(parts) > 1:
            try:
                duration = int(parts[1])
            except ValueError:
                pass

        contest_service.duration = duration
        contest_service.start(message.chat.id)

        text = (
            f"{PARTY} <b>Конкурс начался!</b> {DIAMOND}\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n\n"
            f"Отправьте любое сообщение, чтобы стать лидером.\n"
            f"Кто продержится до конца — получит приз! {TROPHY}{GIFT}"
        )

        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(sent.message_id)

        try:
            await message.bot.set_chat_permissions(
                chat_id=message.chat.id,
                permissions=ChatPermissions(can_send_messages=True),
            )
        except Exception as e:
            await message.answer(f"⚠️ Не удалось открыть чат: {e}")

    @dp.message(Command("stop_contest"))
    async def cmd_stop(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор.")
            return

        contest_service.stop()

        try:
            await message.bot.set_chat_permissions(
                chat_id=message.chat.id,
                permissions=ChatPermissions(can_send_messages=True),
            )
        except Exception:
            pass

        await message.answer("🛑 Конкурс остановлен. Чат открыт. 🔓")

    @dp.message(Command("unlock"))
    async def cmd_unlock(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer(" Только администратор.")
            return

        try:
            await message.bot.set_chat_permissions(
                chat_id=message.chat.id,
                permissions=ChatPermissions(can_send_messages=True),
            )
            await message.answer("✅ Чат открыт. Все могут писать! 🔓")
        except Exception as e:
            await message.answer(f"⚠️ Ошибка: {e}")

    @dp.message(Command("status"))
    async def cmd_status(message: Message):
        if not contest_service.is_active:
            await message.answer("Конкурс не активен. Используйте /start_contest")
            return

        remaining = contest_service.get_remaining_seconds()
        await message.answer(
            f"{STAR} <b>Статус конкурса</b>\n\n"
            f"{CROWN} Лидер: @{contest_service.state['leader_username'] or 'неизвестно'}\n"
            f"{CLOCK} Осталось: {format_time_left(int(remaining))}",
            parse_mode=ParseMode.HTML,
        )