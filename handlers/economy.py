import asyncio
import random
import time
import html as html_module
import logging
from aiogram import F
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus

from services.economy import load_data, save_data, get_or_create_user, format_time
from config import ADMIN_IDS

logger = logging.getLogger(__name__)
active_summons = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def is_chat_admin(bot, user_id: int, chat_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


def get_name_by_id(data, user_id, fallback_username=None):
    uid_str = str(user_id)
    if uid_str in data["users"]:
        u = data["users"][uid_str]
        if u.get("username"): return f"@{html_module.escape(u['username'])}"
    if fallback_username: return f"@{html_module.escape(fallback_username)}"
    return f"id{user_id}"


def safe_text(text: str) -> str:
    return html_module.escape(str(text))


def register_economy_handlers(dp, bot):
    # РАБОТАЕТ С /, ! ИЛИ ВООБЩЕ БЕЗ НИХ
    @dp.message(F.text.regexp(r'(?i)^[/!]?открыть$|^[/!]?open$'))
    async def cmd_open(message: Message):
        try:
            data = load_data()
            user = get_or_create_user(data, message.from_user.id, message.from_user.username)
            now = time.time()
            remaining = 5 * 60 * 60 - (now - user.get("last_chest", 0))
            if remaining > 0:
                await message.answer(f"⏳ Открытие доступно через {format_time(remaining)}")
                return
            roll = random.randint(1, 100)
            is_golden = roll > 92
            reward = random.randint(10, 100) if is_golden else random.randint(1, 10)
            user["coins"] = user.get("coins", 0) + reward
            user["last_chest"] = now
            save_data(data)
            if is_golden:
                await message.answer(f"✨ <b>ЗОЛОТОЙ СУНДУК!</b> 🔑\n💥 Тебе выпало: <b>{reward}</b> coin 🪙",
                                     parse_mode="HTML")
            else:
                await message.answer(f"🎁 <b>Сундук открыт!</b>\n🎉 Тебе выпало: <b>{reward}</b> coin 🪙",
                                     parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка open: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?помощь$|^[/!]?команды$|^[/!]?help$'))
    async def cmd_help(message: Message):
        help_text = (
            "<b>КОМАНДЫ БОТА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Экономика:</b>\n"
            "открыть (или /open, !открыть) — сундук\n"
            "карман (или /pocket) — баланс\n"
            "топ (или /top) — топ-10 богачей\n\n"
            "<b>Созывы:</b>\n"
            "all [текст] — созыв всех\n"
            "admins [текст] — созыв админов\n"
            "стоп — остановить созыв\n\n"
            "<b>Позывные:</b>\n"
            "me — мой позывной\n"
            "setme эмодзи — установить\n"
            "changeme — случайный"
        )
        await message.answer(help_text, parse_mode="HTML")

    @dp.message(F.text.regexp(r'(?i)^[/!]?карман$|^[/!]?pocket$|^[/!]?посмотреть$'))
    async def cmd_pocket(message: Message):
        try:
            data = load_data()
            target = message.reply_to_message.from_user if message.reply_to_message else message.from_user
            target_user = get_or_create_user(data, target.id, target.username)
            name = f"@{target.username}" if getattr(target, 'username', None) else f"id{target.id}"
            await message.answer(f"💰 <b>Карман {safe_text(name)}</b>\n\n{target_user.get('coins', 0)} coin 🪙",
                                 parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка pocket: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?топ$'))
    async def cmd_top(message: Message):
        try:
            data = load_data()
            users_list = [{"username": udata.get("username", f"id{uid}"), "coins": udata.get("coins", 0)} for uid, udata
                          in data["users"].items()]
            users_list.sort(key=lambda x: x["coins"], reverse=True)
            top10 = users_list[:10]
            if not top10 or top10[0]["coins"] == 0:
                await message.answer("📊 Топ пока пуст. Открывай сундуки!")
                return
            msg = "💰 <b>ТОП-10 ПО КОИНАМ</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, u in enumerate(top10):
                prefix = medals[i] if i < 3 else f"{i + 1}."
                msg += f"{prefix} {safe_text(u['username'])} — <b>{u['coins']}</b> 🪙\n"
            await message.answer(msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка top: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?me$|^[/!]?позывной$'))
    async def cmd_me(message: Message):
        try:
            data = load_data()
            user = get_or_create_user(data, message.from_user.id, message.from_user.username)
            call_sign = user.get("call_sign")
            if call_sign:
                await message.answer(f"📛 Твой позывной: {call_sign}\n👤 Имя: {safe_text(message.from_user.full_name)}")
            else:
                await message.answer(
                    f"👤 Имя: {safe_text(message.from_user.full_name)}\n💡 Установи: <code>setme 🔥</code>",
                    parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка me: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?setme\s+(.+)$'))
    async def cmd_setme(message: Message):
        try:
            parts = message.text.split()
            emoji = parts[1]
            if len(emoji) > 8:
                await message.answer("❌ Позывной должен быть коротким.")
                return
            data = load_data()
            user = get_or_create_user(data, message.from_user.id, message.from_user.username)
            user["call_sign"] = emoji
            save_data(data)
            await message.answer(f"✅ Твой новый позывной: {emoji}")
        except Exception as e:
            logger.error(f"Ошибка setme: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?changeme$'))
    async def cmd_changeme(message: Message):
        try:
            emojis = ["🔥", "💎", "🐺", "🦊", "🐻", "🦁", "🐯", "🐲", "👻", "🤖", "👽", "🎯", "💀", "👑", "🎭", "🦅", "🦈", "🐍"]
            emoji = random.choice(emojis)
            data = load_data()
            user = get_or_create_user(data, message.from_user.id, message.from_user.username)
            user["call_sign"] = emoji
            save_data(data)
            await message.answer(f"✅ Твой новый позывной: {emoji}")
        except Exception as e:
            logger.error(f"Ошибка changeme: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?all(\s+.*)?$'))
    async def cmd_all(message: Message):
        try:
            if message.chat.type not in ["group", "supergroup"]:
                await message.answer("❌ Только в группах!");
                return
            if not is_admin(message.from_user.id) and not await is_chat_admin(bot, message.from_user.id,
                                                                              message.chat.id):
                await message.answer("❌ Только для админов!");
                return
            parts = message.text.split()
            call_text = " ".join(parts[1:]) if len(parts) > 1 else "📢 Общий сбор!"
            await message.answer(f"🔄 Начинаю созыв...\n⚠️ Для остановки: <code>стоп</code>", parse_mode="HTML")
            asyncio.create_task(_summon_all(bot, message.chat.id, call_text, message.from_user.id))
        except Exception as e:
            logger.error(f"Ошибка all: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?stop$|^[/!]?стоп$'))
    async def cmd_stop(message: Message):
        if active_summons.get(message.chat.id, False):
            active_summons[message.chat.id] = False
            await message.answer("⏹️ Созыв остановлен.")
        else:
            await message.answer("❌ Активных созывов нет.")

    @dp.message(F.text.regexp(r'(?i)^[/!]?admins(\s+.*)?$'))
    async def cmd_admins(message: Message):
        try:
            parts = message.text.split()
            call_text = " ".join(parts[1:]) if len(parts) > 1 else "📢 Сбор админов!"
            members = await bot.get_chat_administrators(chat_id=message.chat.id)
            admins = [m.user for m in members if not m.user.is_bot]
            if not admins:
                await message.answer("❌ Админы не найдены.");
                return
            mentions = [f"[{u.full_name[:20]}](tg://user?id={u.id})" for u in admins]
            await message.answer(f"📢 {call_text}\n\n" + ", ".join(mentions), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка admins: {e}")

    @dp.message(F.text.regexp(r'(?i)^[/!]?add(\s+.*)?$|^[/!]?пополнить(\s+.*)?$'))
    async def cmd_admin_add(message: Message):
        try:
            if not is_admin(message.from_user.id):
                await message.answer("❌ Только для админов!");
                return
            parts = message.text.split()
            target_user = message.reply_to_message.from_user if (
                        message.reply_to_message and message.reply_to_message.from_user) else None
            amount = 0
            if target_user and len(parts) >= 2:
                try:
                    amount = int(parts[1])
                except:
                    await message.answer("❌ Укажи число"); return
            elif len(parts) == 3:
                try:
                    amount = int(parts[2])
                except:
                    await message.answer("❌ Укажи число"); return
                target_user = message.from_user
            else:
                await message.answer("❌ Формат: ответь на сообщение и напиши <code>add 500</code>", parse_mode="HTML");
                return
            data = load_data()
            target_data = get_or_create_user(data, target_user.id, target_user.username)
            target_data["coins"] += amount
            save_data(data)
            target_name = get_name_by_id(data, target_user.id, target_user.username)
            await message.answer(f"💰 <b>Карман пополнен!</b>\n👤 Кому: {target_name}\n➕ Начислено: <b>{amount}</b> 🪙",
                                 parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка add: {e}")


async def _summon_all(bot, chat_id: int, call_text: str, starter_id: int):
    active_summons[chat_id] = True
    try:
        data = load_data()
        users_to_tag = [int(uid_str) for uid_str in data["users"].keys() if int(uid_str) != starter_id]
        random.shuffle(users_to_tag)
        if not users_to_tag:
            await bot.send_message(chat_id, "❌ Некого созывать.")
            return
        for i in range(0, len(users_to_tag), 15):
            if not active_summons.get(chat_id, False):
                await bot.send_message(chat_id, "⏹️ Созыв остановлен.")
                break
            batch = users_to_tag[i:i + 15]
            mentions = [f"[Пользователь](tg://user?id={uid})" for uid in batch]
            full_text = f"📢 {call_text}\n\n" + "\n".join(mentions)
            await bot.send_message(chat_id, full_text, parse_mode="Markdown")
            await asyncio.sleep(1.5)
    except Exception as e:
        logger.error(f"Ошибка созыва: {e}")
    finally:
        if chat_id in active_summons:
            del active_summons[chat_id]