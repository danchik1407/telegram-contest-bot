from aiogram import F
from aiogram.types import Message, ChatPermissions, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

from services.contest import ContestManager
from utils.formatters import format_time_left


def register_command_handlers(dp, contest_manager: ContestManager, admin_ids: list):
    @dp.message(Command("start_play"))
    async def cmd_start_play(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer(" Только администратор может запустить игру.")
            return

        service = contest_manager.get_service(message.chat.id)

        if service.is_active:
            await message.answer("⚠️ Игра уже идёт в этом чате! Сначала: /stop_play")
            return

        parts = message.text.split()
        duration = service.duration
        prize = "Сюрприз"

        if len(parts) > 1:
            try:
                duration = int(parts[1])
            except ValueError:
                await message.answer("⚠️ Неверный таймер. Пример: /start_play 120 NFT")
                return

        if len(parts) > 2:
            prize = " ".join(parts[2:])

        service.state["pending_duration"] = duration
        service.state["prize"] = prize
        service.state["chat_id"] = message.chat.id

        text = (
            f"🎮 <b>Настройка игры</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n\n"
            f"Могут ли администраторы участвовать в перебиве?"
        )

        # ИСПРАВЛЕНО: используем хэш chat_id для callback_data
        chat_hash = str(abs(message.chat.id))[:10]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, все участвуют", callback_data=f"ay_{chat_hash}"),
                InlineKeyboardButton(text="❌ Нет, только обычные", callback_data=f"an_{chat_hash}"),
            ]
        ])

        sent = await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        service.set_start_message(sent.message_id)

        try:
            await message.delete()
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("ay_"))
    async def callback_admins_yes(callback: CallbackQuery):
        chat_hash = callback.data.split("_")[1]

        # Находим chat_id по хэшу
        chat_id = None
        for cid, service in contest_manager._services.items():
            if str(abs(cid))[:10] == chat_hash:
                chat_id = cid
                break

        if chat_id is None:
            await callback.answer("️ Ошибка: чат не найден.", show_alert=True)
            return

        service = contest_manager.get_service(chat_id)

        if callback.from_user.id not in admin_ids:
            await callback.answer("❌ Только администратор.", show_alert=True)
            return

        if service.is_active:
            await callback.answer("⚠️ Игра уже запущена!", show_alert=True)
            return

        duration = service.state.get("pending_duration", service.duration)
        prize = service.state.get("prize", "Сюрприз")

        service.start(chat_id, duration, prize, admins_allowed=True)

        text = (
            f"🎮 <b>Игра запущена!</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"✅ Задача: продержать своё сообщение самым последним, без перебивов.\n\n"
            f"👥 Участники: <b>Все</b> (включая администраторов)\n\n"
            f"Удачи в бою ☘️"
        )

        await callback.message.edit_text(text, parse_mode=ParseMode.HTML)

        timer_text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f"⏰ До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Чтобы перебить лидера, отправьте любое сообщение 🚀"
        )
        sent = await callback.message.answer(timer_text, parse_mode=ParseMode.HTML)
        service.set_bot_message(sent.message_id)

        await callback.answer()

    @dp.callback_query(F.data.startswith("an_"))
    async def callback_admins_no(callback: CallbackQuery):
        chat_hash = callback.data.split("_")[1]

        chat_id = None
        for cid, service in contest_manager._services.items():
            if str(abs(cid))[:10] == chat_hash:
                chat_id = cid
                break

        if chat_id is None:
            await callback.answer("⚠️ Ошибка: чат не найден.", show_alert=True)
            return

        service = contest_manager.get_service(chat_id)

        if callback.from_user.id not in admin_ids:
            await callback.answer("❌ Только администратор.", show_alert=True)
            return

        if service.is_active:
            await callback.answer("⚠️ Игра уже запущена!", show_alert=True)
            return

        duration = service.state.get("pending_duration", service.duration)
        prize = service.state.get("prize", "Сюрприз")

        service.start(chat_id, duration, prize, admins_allowed=False)

        text = (
            f"🎮 <b>Игра запущена!</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"✅ Задача: продержать своё сообщение самым последним, без перебивов.\n\n"
            f"👥 Участники: <b>Только обычные пользователи</b> (админы и создатель исключены)\n\n"
            f"Удачи в бою ☘️"
        )

        await callback.message.edit_text(text, parse_mode=ParseMode.HTML)

        timer_text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f"⏰ До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Чтобы перебить лидера, отправьте любое сообщение "
        )
        sent = await callback.message.answer(timer_text, parse_mode=ParseMode.HTML)
        service.set_bot_message(sent.message_id)

        await callback.answer()

    @dp.message(Command("play_game"))
    async def cmd_play_game(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор.")
            return

        service = contest_manager.get_service(message.chat.id)

        if service.is_active:
            await message.answer("⚠️ Игра уже идёт в этом чате! /stop_play")
            return

        duration = service.duration
        prize = service.state.get("prize", "Сюрприз")

        service.start(message.chat.id, duration, prize, admins_allowed=True)

        text = (
            f"🎮 <b>Игра запущена!</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"✅ Задача: продержать своё сообщение самым последним, без перебивов.\n\n"
            f"👥 Участники: <b>Все</b> (включая администраторов)\n\n"
            f"Удачи в бою ☘️"
        )
        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        service.set_start_message(sent.message_id)

        timer_text = (
            f" <b>Конкурс!</b>\n\n"
            f"⏰ До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Чтобы перебить лидера, отправьте любое сообщение 🚀"
        )
        timer_sent = await message.answer(timer_text, parse_mode=ParseMode.HTML)
        service.set_bot_message(timer_sent.message_id)

        try:
            await message.delete()
        except Exception:
            pass

    @dp.message(Command("block_admin"))
    async def cmd_block_admin(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор.")
            return

        service = contest_manager.get_service(message.chat.id)

        if service.is_active:
            await message.answer("️ Игра уже идёт в этом чате! /stop_play")
            return

        duration = service.duration
        prize = service.state.get("prize", "Сюрприз")

        service.start(message.chat.id, duration, prize, admins_allowed=False)

        text = (
            f"🎮 <b>Игра запущена!</b>\n\n"
            f"⏱ Длительность: <b>{format_time_left(duration)}</b>\n"
            f"🎁 Приз: <b>{prize}</b>\n"
            f"✅ Задача: продержать своё сообщение самым последним, без перебивов.\n\n"
            f"👥 Участники: <b>Только обычные пользователи</b> (админы и создатель исключены)\n\n"
            f"Удачи в бою ☘️"
        )
        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        service.set_start_message(sent.message_id)

        timer_text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f"⏰ До конца: <b>{format_time_left(duration)}</b>\n\n"
            f"Чтобы перебить лидера, отправьте любое сообщение "
        )
        timer_sent = await message.answer(timer_text, parse_mode=ParseMode.HTML)
        service.set_bot_message(timer_sent.message_id)

        try:
            await message.delete()
        except Exception:
            pass

    @dp.message(Command("stop_play"))
    async def cmd_stop_play(message: Message):
        if message.from_user.id not in admin_ids:
            await message.answer("❌ Только администратор.")
            return

        service = contest_manager.get_service(message.chat.id)

        if not service.is_active:
            await message.answer("Игра не активна в этом чате.")
            return

        service.stop()

        await message.answer("🛑 Перебив завершён.")

        try:
            await message.delete()
        except Exception:
            pass

    @dp.message(Command("status"))
    async def cmd_status(message: Message):
        service = contest_manager.get_service(message.chat.id)

        if not service.is_active:
            await message.answer("Игра не активна в этом чате. /start_play")
            return

        remaining = service.get_remaining_seconds()
        admins_text = "Все" if service.state["admins_allowed"] else "Только обычные"
        await message.answer(
            f"📊 <b>Статус игры</b>\n\n"
            f"👑 Лидер: @{service.state['leader_username'] or 'неизвестно'}\n"
            f"⏰ Осталось: {format_time_left(int(remaining))}\n"
            f"👥 Участники: {admins_text}",
            parse_mode=ParseMode.HTML,
        )

        try:
            await message.delete()
        except Exception:
            pass