from aiogram import F
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ParseMode

from services.contest import ContestService
from utils.formatters import format_time_left, message_link
from utils.emoji import TROPHY, DIAMOND, FIRE, ROCKET, CROWN, GIFT, CLOCK, PARTY, SPARKLES, MEDAL


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
            f"{CLOCK} <b>Конкурс!</b> {DIAMOND}\n\n"
            f"{CROWN} Лидер: <a href='tg://user?id={contest_service.state['leader_id']}'>"
            f"{contest_service.state['leader_username'] or 'участник'}</a>\n"
            f"{CLOCK} До конца: <b>{format_time_left(remaining)}</b>\n\n"
            f"Отправьте любое сообщение, чтобы перебить лидера! {ROCKET}"
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
                print(f"Ошибка обновления таймера: {e}")

    async def announce_winner():
        contest_service.stop()

        chat_id = contest_service.state["chat_id"]
        winner_id = contest_service.state["leader_id"]
        winner_msg_id = contest_service.state["leader_message_id"]
        bot_msg_id = contest_service.state["bot_message_id"]

        link = message_link(chat_id, winner_msg_id)

        text = (
            f"{TROPHY} <b>ПОБЕДИТЕЛЬ КОНКУРСА!</b> {DIAMOND}\n\n"
            f"{CROWN} <a href='tg://user?id={winner_id}'>"
            f"{contest_service.state['leader_username'] or 'Участник'}</a> "
            f"удержал лидерство и забирает приз!\n\n"
            f"🔗 <a href='{link}'>Ссылка на победное сообщение</a>\n\n"
            f"{GIFT} Приз выдаётся вручную администратором.\n\n"
            f"🔒 Чат закрыт — писать могут только админы и владелец."
        )

        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_msg_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

        try:
            await bot.set_chat_permissions(
                chat_id=chat_id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            await bot.send_message(
                chat_id=chat_id,
                text="🔒 Чат заблокирован. Обычные участники не могут писать.",
            )
        except Exception as e:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ Бот не имеет прав администратора: {e}",
            )

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

        contest_service.set_leader(
            user_id=message.from_user.id,
            username=message.from_user.username,
            message_id=message.message_id,
        )

        text = (
            f"{FIRE} <b>Перебито!</b> {DIAMOND}\n\n"
            f"{CROWN} Новый лидер: "
            f"<a href='tg://user?id={message.from_user.id}'>"
            f"@{message.from_user.username or message.from_user.first_name}</a>\n"
            f"{CLOCK} До конца: <b>{format_time_left(contest_service.duration)}</b>\n\n"
            f"Отправьте сообщение, чтобы забрать приз! {GIFT}"
        )

        old_bot_msg_id = contest_service.state["bot_message_id"]

        if old_bot_msg_id is not None:
            try:
                await bot.delete_message(
                    chat_id=contest_service.state["chat_id"],
                    message_id=old_bot_msg_id,
                )
            except Exception as e:
                print(f"Не удалось удалить старое сообщение: {e}")

        sent = await message.answer(text, parse_mode=ParseMode.HTML)
        contest_service.set_bot_message(sent.message_id)

        await contest_service.start_timer_task(on_timer_update)