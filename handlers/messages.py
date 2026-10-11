from aiogram import F
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ParseMode

from services.contest import ContestService
from utils.formatters import format_time_left, message_link


def register_message_handlers(dp, contest_service: ContestService, bot):
    async def on_timer_update(remaining: int, finished: bool = False):
        if finished:
            await announce_winner()
            return

        chat_id = contest_service.state["chat_id"]
        bot_msg_id = contest_service.state["bot_message_id"]

        if not bot_msg_id:
            return

        text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f"👑 Лидер: <a href='tg://user?id={contest_service.state['leader_id']}'>"
            f"{contest_service.state['leader_username'] or 'участник'}</a>\n"
            f"⏰ До конца: <b>{format_time_left(remaining)}</b>\n\n"
            f"Отправьте сообщение, чтобы перебить лидера! 🚀"
        )

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_msg_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                print(f"Ошибка таймера: {e}")

    async def announce_winner():
        """Объявление победителя с подробным логированием."""
        print("🏆 [ANNOUNCE] Начинаем объявление победителя...")

        try:
            contest_service.stop()
            print("✅ [ANNOUNCE] Конкурс остановлен")

            chat_id = contest_service.state["chat_id"]
            winner_id = contest_service.state["leader_id"]
            winner_msg_id = contest_service.state["leader_message_id"]
            bot_msg_id = contest_service.state["bot_message_id"]
            prize = contest_service.state.get("prize", "Сюрприз")
            winner_username = contest_service.state.get("leader_username", "Участник")

            print(f"📊 [ANNOUNCE] chat_id={chat_id}, winner_id={winner_id}, winner_msg_id={winner_msg_id}")

            # Безопасное получение ссылки
            link = "неизвестно"
            if winner_msg_id:
                try:
                    link = message_link(chat_id, winner_msg_id)
                    print(f"🔗 [ANNOUNCE] Ссылка: {link}")
                except Exception as e:
                    print(f"⚠️ [ANNOUNCE] Ошибка создания ссылки: {e}")

            text = (
                f" <b>ПОБЕДИТЕЛЬ КОНКУРСА!</b>\n\n"
                f" <a href='tg://user?id={winner_id}'>"
                f"{winner_username}</a> "
                f"удержал лидерство и забирает приз!\n\n"
                f"🎁 Приз: <b>{prize}</b>\n\n"
                f"🔗 <a href='{link}'>Ссылка на победное сообщение</a>\n\n"
                f"Приз выдаётся вручную администратором.\n\n"
                f"🔒 Чат закрыт — писать могут только админы и владелец."
            )

            # Удаляем сообщение с таймером
            if bot_msg_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=bot_msg_id)
                    print("✅ [ANNOUNCE] Старое сообщение с таймером удалено")
                except Exception as e:
                    print(f"⚠️ [ANNOUNCE] Не удалось удалить сообщение: {e}")

            # Отправляем сообщение о победителе
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                print("✅ [ANNOUNCE] Сообщение о победителе отправлено")
            except Exception as e:
                print(f"❌ [ANNOUNCE] Ошибка отправки сообщения: {e}")

            # Закрываем чат
            try:
                await bot.set_chat_permissions(
                    chat_id=chat_id,
                    permissions=ChatPermissions(can_send_messages=False),
                )
                print("✅ [ANNOUNCE] Чат заблокирован")
            except Exception as e:
                print(f"️ [ANNOUNCE] Не удалось заблокировать чат: {e}")

        except Exception as e:
            print(f"❌ [ANNOUNCE] КРИТИЧЕСКАЯ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()

    @dp.message(F.chat.type.in_(["group", "supergroup"]))
    async def on_message(message: Message):
        if message.from_user.is_bot:
            return

        if message.text and message.text.startswith("/"):
            return

        if not contest_service.is_active:
            return

        if message.chat.id != contest_service.state["chat_id"]:
            return

        # ПРОВЕРКА 1: Тот же лидер — игнорируем (таймер НЕ сбрасывается)
        if contest_service.is_same_leader(message.from_user.id):
            return

        # ПРОВЕРКА 2: Админы и создатель не участвуют
        if not contest_service.state["admins_allowed"]:
            try:
                member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                # Блокируем и administrator (зелёный тег), и creator (фиолетовый тег/владелец)
                if member.status in ("administrator", "creator"):
                    return
            except Exception:
                pass

        # Новый лидер!
        contest_service.set_leader(
            user_id=message.from_user.id,
            username=message.from_user.username,
            message_id=message.message_id,
        )

        text = (
            f"🔄 <b>Перебито!</b>\n\n"
            f"👑 Новый лидер: "
            f"<a href='tg://user?id={message.from_user.id}'>"
            f"@{message.from_user.username or message.from_user.first_name}</a>\n"
            f"⏰ До конца: <b>{format_time_left(contest_service.duration)}</b>\n\n"
            f"Отправьте сообщение, чтобы забрать приз! 🎁"
        )

        old_bot_msg_id = contest_service.state["bot_message_id"]

        # Удаляем СТАРОЕ сообщение с таймером (не стартовое!)
        if old_bot_msg_id is not None:
            try:
                await bot.delete_message(
                    chat_id=contest_service.state["chat_id"],
                    message_id=old_bot_msg_id,
                )
            except Exception as e:
                print(f"Не удалось удалить: {e}")

        # Отправляем новое сообщение с таймером
        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(sent.message_id)

        # Запускаем таймер
        await contest_service.start_timer_task(on_timer_update)