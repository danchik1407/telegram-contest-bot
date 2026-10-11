from aiogram import F
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ParseMode

from services.contest import ContestService
from utils.formatters import format_time_left, message_link


def register_message_handlers(dp, contest_service: ContestService, bot):
    async def on_timer_update(remaining: int, finished: bool = False):
        print(f"⏰ [TIMER] on_timer_update: remaining={remaining}, finished={finished}")

        if finished:
            print(" [TIMER] Время вышло! Вызываем announce_winner()...")
            await announce_winner()
            return

        chat_id = contest_service.state["chat_id"]
        bot_msg_id = contest_service.state["bot_message_id"]

        if not bot_msg_id:
            print("⚠️ [TIMER] bot_msg_id отсутствует")
            return

        text = (
            f"⏳ <b>Конкурс!</b>\n\n"
            f" Лидер: <a href='tg://user?id={contest_service.state['leader_id']}'>"
            f"{contest_service.state['leader_username'] or 'участник'}</a>\n"
            f"⏰ До конца: <b>{format_time_left(remaining)}</b>\n\n"
            f"Отправьте сообщение, чтобы перебить лидера! "
        )

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_msg_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            print(f"✅ [TIMER] Таймер обновлен: {remaining} сек")
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                print(f" [TIMER] Ошибка: {e}")

    async def announce_winner():
        print("🏆 [ANNOUNCE] === НАЧИНАЕМ ОБЪЯВЛЕНИЕ ПОБЕДИТЕЛЯ ===")

        try:
            chat_id = contest_service.state["chat_id"]
            winner_id = contest_service.state["leader_id"]
            winner_msg_id = contest_service.state["leader_message_id"]
            bot_msg_id = contest_service.state["bot_message_id"]
            prize = contest_service.state.get("prize", "Сюрприз")
            winner_username = contest_service.state.get("leader_username", "Участник")

            print(f"📊 [ANNOUNCE] chat_id={chat_id}")
            print(f"📊 [ANNOUNCE] winner_id={winner_id}")
            print(f"📊 [ANNOUNCE] winner_username={winner_username}")
            print(f"📊 [ANNOUNCE] winner_msg_id={winner_msg_id}")
            print(f"📊 [ANNOUNCE] bot_msg_id={bot_msg_id}")
            print(f"📊 [ANNOUNCE] prize={prize}")

            # Ссылка на сообщение
            link = "неизвестно"
            if winner_msg_id:
                try:
                    link = message_link(chat_id, winner_msg_id)
                    print(f" [ANNOUNCE] Ссылка: {link}")
                except Exception as e:
                    print(f"⚠️ [ANNOUNCE] Ошибка ссылки: {e}")

            text = (
                f"🏆 <b>ПОБЕДИТЕЛЬ КОНКУРСА!</b>\n\n"
                f"👑 <a href='tg://user?id={winner_id}'>"
                f"{winner_username}</a> "
                f"удержал лидерство и забирает приз!\n\n"
                f"🎁 Приз: <b>{prize}</b>\n\n"
                f" <a href='{link}'>Ссылка на победное сообщение</a>\n\n"
                f"Приз выдаётся вручную администратором."
            )

            # Удаляем таймер
            if bot_msg_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=bot_msg_id)
                    print("✅ [ANNOUNCE] Таймер удален")
                except Exception as e:
                    print(f"⚠️ [ANNOUNCE] Не удалил таймер: {e}")

            # ОТПРАВЛЯЕМ СООБЩЕНИЕ О ПОБЕДИТЕЛЕ
            print("📤 [ANNOUNCE] Отправляем сообщение о победителе...")
            try:
                result = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                print(f"✅ [ANNOUNCE] СООБЩЕНИЕ ОТПРАВЛЕНО! message_id={result.message_id}")

                # ЗАКРЕПЛЯЕМ СООБЩЕНИЕ О ПОБЕДИТЕЛЕ
                try:
                    await bot.pin_chat_message(
                        chat_id=chat_id,
                        message_id=result.message_id,
                        disable_notification=False,
                    )
                    print("✅ [ANNOUNCE] Сообщение о победителе ЗАКРЕПЛЕНО!")
                except Exception as e:
                    print(f"️ [ANNOUNCE] Не удалось закрепить сообщение: {e}")

            except Exception as e:
                print(f"❌ [ANNOUNCE] ОШИБКА ОТПРАВКИ: {e}")
                import traceback
                traceback.print_exc()

            # ПОЛНОСТЬЮ ОСТАНАВЛИВАЕМ КОНКУРС
            contest_service.stop()
            print("✅ [ANNOUNCE] Конкурс полностью остановлен")

            # Сбрасываем состояние
            contest_service.state["active"] = False
            contest_service.state["ended"] = True
            contest_service.state["leader_id"] = None
            contest_service.state["leader_username"] = None
            contest_service.state["leader_message_id"] = None
            contest_service.state["bot_message_id"] = None
            contest_service.state["end_time"] = None

            print("✅ [ANNOUNCE] Состояние полностью сброшено")
            print("✅ [ANNOUNCE] Чат остается открытым")
            print("🏆 [ANNOUNCE] === ЗАВЕРШЕНО ===")

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

        # ПРОВЕРКА: Конкурс не активен — игнорируем
        if not contest_service.is_active:
            return

        if message.chat.id != contest_service.state["chat_id"]:
            return

        # Тот же лидер — игнорируем
        if contest_service.is_same_leader(message.from_user.id):
            return

        # Админы не участвуют
        if not contest_service.state["admins_allowed"]:
            try:
                member = await bot.get_chat_member(message.chat.id, message.from_user.id)
                if member.status in ("administrator", "creator"):
                    return
            except Exception:
                pass

        # Новый лидер
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

        if old_bot_msg_id is not None:
            try:
                await bot.delete_message(
                    chat_id=contest_service.state["chat_id"],
                    message_id=old_bot_msg_id,
                )
            except Exception as e:
                print(f"Не удалил старое: {e}")

        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(sent.message_id)

        print(f"🚀 [MESSAGE] Запускаем таймер для нового лидера")
        await contest_service.start_timer_task(on_timer_update)