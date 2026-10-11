from aiogram import F
from aiogram.types import Message
from aiogram.enums import ParseMode

from services.contest import ContestManager
from utils.formatters import format_time_left, message_link


def register_message_handlers(dp, contest_manager: ContestManager, bot):
    async def on_timer_update(service, remaining: int, finished: bool = False):
        print(f"⏰ [TIMER] chat={service.state['chat_id']}, remaining={remaining}, finished={finished}")

        if finished:
            print("🏆 [TIMER] Время вышло! Вызываем announce_winner()...")
            await announce_winner(service)
            return

        chat_id = service.state["chat_id"]
        bot_msg_id = service.state["bot_message_id"]

        if not bot_msg_id:
            return

        username = service.state['leader_username'] or 'участник'
        if not username.startswith('@') and not username.startswith('tg://'):
            username = f"@{username}"

        text = (
            f"<b>Перебито ✅️</b>\n\n"
            f" Лидер: <a href='tg://user?id={service.state['leader_id']}'>{username}</a>\n"
            f"⏰ Продержаться: <b>{format_time_left(remaining)}</b>\n\n"
            f"Чтобы перебить лидера, отправьте любое сообщение 🚀"
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
                print(f" [TIMER] Ошибка: {e}")

    async def announce_winner(service):
        print(f" [ANNOUNCE] chat={service.state['chat_id']}")

        try:
            chat_id = service.state["chat_id"]
            winner_id = service.state["leader_id"]
            winner_msg_id = service.state["leader_message_id"]
            bot_msg_id = service.state["bot_message_id"]
            prize = service.state.get("prize", "Сюрприз")
            winner_username = service.state.get("leader_username", "Участник")

            link = "неизвестно"
            if winner_msg_id:
                try:
                    link = message_link(chat_id, winner_msg_id)
                except Exception as e:
                    print(f"⚠️ [ANNOUNCE] Ошибка ссылки: {e}")

            text = (
                f"🏆 <b>ПОБЕДИТЕЛЬ:</b> <a href='tg://user?id={winner_id}'>{winner_username}</a> удержавший последнее сообщение 👑\n\n"
                f"🎁 Приз: <b>{prize}</b>\n\n"
                f" <a href='{link}'>Ссылка на победное сообщение</a>\n\n"
                f"Приз выдаётся вручную администратором."
            )

            if bot_msg_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=bot_msg_id)
                except Exception as e:
                    print(f"️ [ANNOUNCE] Не удалил таймер: {e}")

            try:
                result = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                print(f"✅ [ANNOUNCE] Сообщение отправлено, id={result.message_id}")

                try:
                    await bot.pin_chat_message(
                        chat_id=chat_id,
                        message_id=result.message_id,
                        disable_notification=False,
                    )
                    print("✅ [ANNOUNCE] Сообщение закреплено!")
                except Exception as e:
                    print(f"⚠️ [ANNOUNCE] Не закрепил: {e}")

            except Exception as e:
                print(f"❌ [ANNOUNCE] ОШИБКА ОТПРАВКИ: {e}")

            service.stop()
            service.state["active"] = False
            service.state["ended"] = True
            service.state["leader_id"] = None
            service.state["leader_username"] = None
            service.state["leader_message_id"] = None
            service.state["bot_message_id"] = None
            service.state["end_time"] = None

            print(f"✅ [ANNOUNCE] Конкурс в чате {chat_id} полностью завершён")

        except Exception as e:
            print(f"❌ [ANNOUNCE] КРИТИЧЕСКАЯ ОШИБКА: {e}")

    @dp.message(F.chat.type.in_(["group", "supergroup"]))
    async def on_message(message: Message):
        if message.from_user.is_bot:
            return

        if message.text and message.text.startswith("/"):
            return

        service = contest_manager.get_service(message.chat.id)

        if not service.is_active:
            return

        if message.chat.id != service.state["chat_id"]:
            return

        if service.is_same_leader(message.from_user.id):
            return

        if not service.state["admins_allowed"]:
            try:
                member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                if member.status in ("administrator", "creator"):
                    return
            except Exception:
                pass

        service.set_leader(
            user_id=message.from_user.id,
            username=message.from_user.username,
            message_id=message.message_id,
        )

        user_display = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

        text = (
            f"<b>Перебито ✅️</b>\n\n"
            f"👑 Лидер: <a href='tg://user?id={message.from_user.id}'>{user_display}</a>\n"
            f"⏰ Продержаться: <b>{format_time_left(service.duration)}</b>\n\n"
            f"Чтобы перебить лидера, отправьте любое сообщение 🚀"
        )

        old_bot_msg_id = service.state["bot_message_id"]

        if old_bot_msg_id is not None:
            try:
                await bot.delete_message(
                    chat_id=service.state["chat_id"],
                    message_id=old_bot_msg_id,
                )
            except Exception as e:
                print(f"Не удалил старое: {e}")

        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        service.set_bot_message(sent.message_id)

        # ИСПРАВЛЕНО: используем functools.partial вместо lambda
        import functools
        callback = functools.partial(on_timer_update, service)
        await service.start_timer_task(callback)