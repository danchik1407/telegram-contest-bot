from aiogram import F
from aiogram.types import Message, ChatPermissions, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

from services.contest import ContestService
from utils.formatters import format_time_left


def register_command_handlers(dp, contest_service: ContestService, admin_ids: list):
    # ─── /start_play [таймер] [приз] ───
    @dp.message(Command("start_play"))
    async def cmd_start_play(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор может запустить игру.")
            return

        if contest_service.is_active:
            await message.answer("⚠️ Игра уже идёт! Сначала: /stop_play")
            return

        parts = message.text.split()
        duration = contest_service.duration
        prize = "Сюрприз"

        if len(parts) > 1:
            try:
                duration = int(parts[1])
            except ValueError:
                await message.answer("⚠️ Неверный таймер. Пример: /start_play 120 NFT")
                return

        if len(parts) > 2:
            prize = " ".join(parts[2:])

        contest_service.state["pending_duration"] = duration
        contest_service.state["prize"] = prize
        contest_service.state["chat_id"] = message.chat.id

        text = (
            f"🎮 <b>Настройка игры</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n\n"
            f"Могут ли администраторы участвовать в перебиве?"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, все участвуют", callback_data="admins_yes"),
                InlineKeyboardButton(text="❌ Нет, только обычные", callback_data="admins_no"),
            ]
        ])

        sent = await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        contest_service.set_start_message(sent.message_id)

    # ── Кнопка: админы участвуют ───
    @dp.callback_query(F.data == "admins_yes")
    async def callback_admins_yes(callback: CallbackQuery):
        if callback.from_user.id not in admin_ids:
            await callback.answer(" Только администратор.", show_alert=True)
            return

        if contest_service.is_active:
            await callback.answer("⚠️ Игра уже запущена!", show_alert=True)
            return

        duration = contest_service.state.get("pending_duration", contest_service.duration)
        prize = contest_service.state.get("prize", "Сюрприз")
        chat_id = contest_service.state.get("chat_id")

        if not chat_id:
            await callback.answer("⚠️ Ошибка: чат не найден.", show_alert=True)
            return

        contest_service.start(chat_id, duration, prize, admins_allowed=True)

        await callback.message.edit_text(
            f"🎮 <b>Игра запущена!</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"👥 Участники: <b>Все</b> (включая администраторов)\n\n"
            f"Отправьте сообщение, чтобы стать лидером! 🏆",
            parse_mode=ParseMode.HTML,
        )

        text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f" До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Отправьте сообщение, чтобы перебить лидера! 🚀"
        )
        sent = await callback.message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(sent.message_id)

        await callback.answer()

    # ─── Кнопка: админы НЕ участвуют ───
    @dp.callback_query(F.data == "admins_no")
    async def callback_admins_no(callback: CallbackQuery):
        if callback.from_user.id not in admin_ids:
            await callback.answer("❌ Только администратор.", show_alert=True)
            return

        if contest_service.is_active:
            await callback.answer("⚠️ Игра уже запущена!", show_alert=True)
            return

        duration = contest_service.state.get("pending_duration", contest_service.duration)
        prize = contest_service.state.get("prize", "Сюрприз")
        chat_id = contest_service.state.get("chat_id")

        if not chat_id:
            await callback.answer("⚠️ Ошибка: чат не найден.", show_alert=True)
            return

        contest_service.start(chat_id, duration, prize, admins_allowed=False)

        await callback.message.edit_text(
            f"🎮 <b>Игра запущена!</b>\n\n"
            f" Длительность: <b>{format_time_left(duration)}</b>\n"
            f" Приз: <b>{prize}</b>\n"
            f"👥 Участники: <b>Только обычные пользователи</b> (админы и создатель исключены)\n\n"
            f"Отправьте сообщение, чтобы стать лидером! 🏆",
            parse_mode=ParseMode.HTML,
        )

        text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f"⏰ До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Отправьте сообщение, чтобы перебить лидера! 🚀"
        )
        sent = await callback.message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(sent.message_id)

        await callback.answer()

    # ─── /play_game (быстрый запуск с админами) ───
    @dp.message(Command("play_game"))
    async def cmd_play_game(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор.")
            return

        if contest_service.is_active:
            await message.answer("⚠️ Игра уже идёт! /stop_play")
            return

        duration = contest_service.duration
        prize = contest_service.state.get("prize", "Сюрприз")

        contest_service.start(message.chat.id, duration, prize, admins_allowed=True)

        text = (
            f"🎮 <b>Игра запущена!</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f" Участники: <b>Все</b>\n\n"
            f"Отправьте сообщение, чтобы стать лидером!"
        )
        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_start_message(sent.message_id)

        timer_text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f"⏰ До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Отправьте сообщение, чтобы перебить лидера! "
        )
        timer_sent = await message.answer(timer_text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(timer_sent.message_id)

    # ─── /block_admin (быстрый запуск без админов и создателя) ──
    @dp.message(Command("block_admin"))
    async def cmd_block_admin(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор.")
            return

        if contest_service.is_active:
            await message.answer("⚠️ Игра уже идёт! /stop_play")
            return

        duration = contest_service.duration
        prize = contest_service.state.get("prize", "Сюрприз")

        contest_service.start(message.chat.id, duration, prize, admins_allowed=False)

        text = (
            f"🎮 <b>Игра запущена!</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"👥 Участники: <b>Только обычные</b> (админы и создатель исключены)\n\n"
            f"Отправьте сообщение, чтобы стать лидером!"
        )
        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_start_message(sent.message_id)

        timer_text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f"⏰ До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Отправьте сообщение, чтобы перебить лидера! 🚀"
        )
        timer_sent = await message.answer(timer_text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(timer_sent.message_id)

    # ─── /stop_play ───
    @dp.message(Command("stop_play"))
    async def cmd_stop_play(message: Message):
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

        await message.answer("🛑 Игра остановлена. Чат открыт. 🔓")

    # ─── /status ───
    @dp.message(Command("status"))
    async def cmd_status(message: Message):
        if not contest_service.is_active:
            await message.answer("Игра не активна. /start_play")
            return

        remaining = contest_service.get_remaining_seconds()
        admins_text = "Все" if contest_service.state["admins_allowed"] else "Только обычные"
        await message.answer(
            f"📊 <b>Статус игры</b>\n\n"
            f"👑 Лидер: @{contest_service.state['leader_username'] or 'неизвестно'}\n"
            f"⏰ Осталось: {format_time_left(int(remaining))}\n"
            f" Участники: {admins_text}",
            parse_mode=ParseMode.HTML,
        )