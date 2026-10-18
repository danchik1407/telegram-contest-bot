import asyncio
import random
import time
import html as html_module
import logging
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus

from services.economy import load_data, save_data, get_or_create_user, format_time
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

active_summons = {}
active_challenges = {}
CHALLENGE_TIMEOUT = 60


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
        if u.get("username"):
            return f"@{html_module.escape(u['username'])}"
    if fallback_username:
        return f"@{html_module.escape(fallback_username)}"
    return f"id{user_id}"


def safe_text(text: str) -> str:
    return html_module.escape(str(text))


def register_economy_handlers(dp, bot):
    # 1. ПОМОЩЬ
    @dp.message(lambda m: m.text and m.text.lower().strip() in ["!помощь", "!команды", "!help"])
    async def cmd_help(message: Message):
        help_text = (
            "📖 <b>СПИСОК КОМАНД</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📦 <code>!открыть</code> — сундук (КД 5ч)\n"
            "💰 <code>!карман</code> / <code>!карман @user</code>\n"
            "💸 <code>!перевод @user сумма</code>\n"
            "🏆 <code>!топ</code> — топ-10 богачей\n"
            "🎲 <code>!кубы @user сумма</code>\n"
            "📢 <code>!all</code> / <code>!admins</code> / <code>!stop</code>\n"
            "📛 <code>!me</code> / <code>!setme эмодзи</code>"
        )
        await message.answer(help_text, parse_mode="HTML")

    # 2. ОТКРЫТЬ СУНДУК
    @dp.message(lambda m: m.text and m.text.lower().strip() == "!открыть")
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
                await message.answer(
                    f"✨ <b>ЗОЛОТОЙ СУНДУК!</b> 🔑\n\n💥 Невероятная удача!\n🎉 Тебе выпало: <b>{reward}</b> coin 🪙",
                    parse_mode="HTML")
            else:
                await message.answer(f"🎁 <b>Сундук открыт!</b>\n\n🎉 Тебе выпало: <b>{reward}</b> coin 🪙",
                                     parse_mode="HTML")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_open: {e}")

    # 3. КАРМАН
    @dp.message(lambda m: m.text and m.text.lower().strip().startswith("!карман") or m.text.lower().strip().startswith(
        "!посмотреть карман"))
    async def cmd_pocket(message: Message):
        try:
            data = load_data()
            target = None

            if message.reply_to_message and message.reply_to_message.from_user:
                target = message.reply_to_message.from_user
            else:
                parts = message.text.strip().split()
                if len(parts) >= 2:
                    username_arg = parts[-1].lstrip("@").lower()
                    for uid_str, udata in data["users"].items():
                        if udata.get("username", "").lower() == username_arg:
                            target = type('User', (), {'id': int(uid_str), 'username': udata.get("username")})()
                            break

            if not target:
                target = message.from_user

            user = get_or_create_user(data, target.id, target.username)
            display_name = f"@{target.username}" if getattr(target, 'username', None) else f"id{target.id}"
            await message.answer(f"💰 <b>Карман {safe_text(display_name)}</b>\n\n{user.get('coins', 0)} coin 🪙",
                                 parse_mode="HTML")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_pocket: {e}")

    # 4. ТОП
    @dp.message(lambda m: m.text and m.text.lower().strip() in ["!топ", "!топ монет"])
    async def cmd_top_coins(message: Message):
        try:
            data = load_data()
            users_list = [{"username": udata.get("username", f"id{uid_str}"), "coins": udata.get("coins", 0)}
                          for uid_str, udata in data["users"].items()]
            users_list.sort(key=lambda x: x["coins"], reverse=True)
            top10 = users_list[:10]

            if not top10 or top10[0]["coins"] == 0:
                await message.answer("📊 Топ пока пуст. Открывай сундуки!")
                return

            msg = "💰 <b>ТОП-10 ПО КОИНАМ</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, u in enumerate(top10):
                prefix = medals[i] if i < 3 else f"{i + 1}."
                name = u['username']
                msg += f"{prefix} {safe_text(name)} — <b>{u['coins']}</b> coin 🪙\n"
            await message.answer(msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_top_coins: {e}")

    # 5. ПЕРЕВОД
    @dp.message(lambda m: m.text and m.text.lower().strip().startswith("!перевод"))
    async def cmd_transfer(message: Message):
        try:
            data = load_data()
            sender = get_or_create_user(data, message.from_user.id, message.from_user.username)
            target_user, amount = None, None

            if message.reply_to_message and message.reply_to_message.from_user:
                target_user = message.reply_to_message.from_user
                parts = message.text.strip().split()
                if len(parts) < 2:
                    await message.answer("❌ Укажи сумму: <code>!перевод 50</code>", parse_mode="HTML")
                    return
                amount = int(parts[1])
            else:
                parts = message.text.strip().split()
                if len(parts) < 3:
                    await message.answer("❌ Формат: <code>!перевод @username 50</code>", parse_mode="HTML")
                    return
                username_arg = parts[1].lstrip("@").lower()
                amount = int(parts[2])
                for uid_str, udata in data["users"].items():
                    if udata.get("username", "").lower() == username_arg:
                        target_user = type('User', (), {'id': int(uid_str), 'username': udata.get("username")})()
                        break
                if not target_user:
                    await message.answer("❌ Пользователь не найден.")
                    return

            if amount <= 0 or target_user.id == message.from_user.id:
                await message.answer("❌ Сумма должна быть > 0 и нельзя переводить самому себе.")
                return
            if sender["coins"] < amount:
                await message.answer(f"❌ Недостаточно коинов. У тебя: <b>{sender['coins']}</b> 🪙", parse_mode="HTML")
                return

            sender["coins"] -= amount
            target = get_or_create_user(data, target_user.id, target_user.username)
            target["coins"] = target.get("coins", 0) + amount
            save_data(data)

            sender_name = f"@{message.from_user.username}" if message.from_user.username else f"id{message.from_user.id}"
            target_name = f"@{target_user.username}" if target_user.username else f"id{target_user.id}"
            await message.answer(
                f"✅ <b>Перевод выполнен!</b>\n\n👤 От: {safe_text(sender_name)}\n👤 Кому: {safe_text(target_name)}\n💸 Сумма: <b>{amount}</b> coin 🪙",
                parse_mode="HTML")
        except ValueError:
            await message.answer("❌ Сумма должна быть числом!")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_transfer: {e}")

    # 6. КУБЫ
    @dp.message(lambda m: m.text and m.text.lower().strip().startswith("!кубы"))
    async def cmd_dice(message: Message):
        try:
            parts = message.text.strip().split()
            target_user = None
            amount = 0

            if message.reply_to_message and message.reply_to_message.from_user:
                target_user = message.reply_to_message.from_user
                if len(parts) >= 2:
                    amount = int(parts[1])
            elif len(parts) >= 3:
                username_arg = parts[1].lstrip("@").lower()
                amount = int(parts[2])
                data = load_data()
                for uid_str, udata in data["users"].items():
                    if udata.get("username", "").lower() == username_arg:
                        target_user = type('User', (), {'id': int(uid_str), 'username': udata.get("username")})()
                        break

            if not target_user or amount <= 0:
                await message.answer(
                    "🎲 Формат: <code>!кубы @user сумма</code> или ответом на сообщение <code>!кубы сумма</code>",
                    parse_mode="HTML")
                return

            if target_user.id == message.from_user.id:
                await message.answer("❌ Нельзя играть с собой!")
                return

            data = load_data()
            challenger = get_or_create_user(data, message.from_user.id, message.from_user.username)
            challenged = get_or_create_user(data, target_user.id, target_user.username)

            if challenger["coins"] < amount:
                await message.answer(f"❌ У тебя мало монет. Нужно: {amount}")
                return
            if challenged["coins"] < amount:
                await message.answer(f"❌ У противника мало монет.")
                return

            challenger["coins"] -= amount
            challenged["coins"] -= amount
            save_data(data)

            c_name = get_name_by_id(data, message.from_user.id, message.from_user.username)
            d_name = get_name_by_id(data, target_user.id, target_user.username)

            await message.answer(
                f"🎲 <b>Дуэль!</b>\n{c_name} против {d_name}\nСтавка: <b>{amount}</b> 🪙\n\nБросаем кубики...",
                parse_mode="HTML")

            dice1 = await bot.send_dice(chat_id=message.chat.id, emoji="🎲")
            await asyncio.sleep(2)
            dice2 = await bot.send_dice(chat_id=message.chat.id, emoji="🎲")
            await asyncio.sleep(1)

            v1, v2 = dice1.dice.value, dice2.dice.value

            if v1 > v2:
                challenger["coins"] += amount * 2
                res = f"🏆 <b>Победил {c_name}!</b> ({v1} vs {v2})\n+{amount * 2} 🪙"
            elif v2 > v1:
                challenged["coins"] += amount * 2
                res = f"🏆 <b>Победил {d_name}!</b> ({v1} vs {v2})\n+{amount * 2} 🪙"
            else:
                challenger["coins"] += amount
                challenged["coins"] += amount
                res = f"🤝 <b>Ничья!</b> ({v1} vs {v2})\nСтавки возвращены."

            save_data(data)
            await message.answer(res, parse_mode="HTML")

            try:
                await bot.delete_message(message.chat.id, dice1.message_id)
                await bot.delete_message(message.chat.id, dice2.message_id)
            except:
                pass
        except ValueError:
            await message.answer("❌ Сумма должна быть числом!")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_dice: {e}")

    # 7. СОЗЫВЫ (!all, !admins, !stop)
    @dp.message(lambda m: m.text and m.text.lower().strip().startswith("!all"))
    async def cmd_all(message: Message):
        try:
            if message.chat.type not in ["group", "supergroup"]:
                await message.answer("❌ Только в группах!")
                return
            user_id = message.from_user.id
            if not is_admin(user_id) and not await is_chat_admin(bot, user_id, message.chat.id):
                await message.answer("❌ Только для админов!")
                return
            parts = message.text.strip().split()
            call_text = " ".join(parts[1:]) if len(parts) > 1 else "📢 Общий сбор!"
            await message.answer(f"🔄 Начинаю созыв...\n⚠️ Для остановки: <code>!stop</code>", parse_mode="HTML")
            asyncio.create_task(_summon_all_members(message.chat.id, call_text, user_id))
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_all: {e}")

    async def _summon_all_members(chat_id: int, call_text: str, starter_id: int):
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
            logger.error(f"[ECONOMY ERROR] _summon: {e}")
        finally:
            if chat_id in active_summons:
                del active_summons[chat_id]

    @dp.message(lambda m: m.text and m.text.lower().strip() in ["!stop", "!стоп"])
    async def cmd_stop(message: Message):
        if active_summons.get(message.chat.id, False):
            active_summons[message.chat.id] = False
            await message.answer("⏹️ Созыв остановлен.")
        else:
            await message.answer("❌ Активных созывов нет.")

    @dp.message(lambda m: m.text and m.text.lower().strip().startswith("!admins"))
    async def cmd_admins(message: Message):
        try:
            parts = message.text.strip().split()
            call_text = " ".join(parts[1:]) if len(parts) > 1 else "📢 Сбор админов!"
            members = await bot.get_chat_administrators(chat_id=message.chat.id)
            admins = [m.user for m in members if not m.user.is_bot]
            if not admins:
                await message.answer("❌ Админы не найдены.")
                return
            mentions = [f"[{u.full_name[:20]}](tg://user?id={u.id})" for u in admins]
            await message.answer(f"📢 {call_text}\n\n" + ", ".join(mentions), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_admins: {e}")

    # 8. ПОЗЫВНЫЕ
    @dp.message(lambda m: m.text and m.text.lower().strip() in ["!me", "!позывной"])
    async def cmd_me(message: Message):
        try:
            data = load_data()
            user = get_or_create_user(data, message.from_user.id, message.from_user.username)
            call_sign = user.get("call_sign")
            if call_sign:
                await message.answer(f"📛 Твой позывной: {call_sign}\n👤 Имя: {safe_text(message.from_user.full_name)}")
            else:
                await message.answer(
                    f"👤 Имя: {safe_text(message.from_user.full_name)}\n💡 Установи: <code>!setme 🔥</code>",
                    parse_mode="HTML")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_me: {e}")

    @dp.message(lambda m: m.text and m.text.lower().strip().startswith("!setme "))
    async def cmd_setme(message: Message):
        try:
            parts = message.text.strip().split()
            if len(parts) < 2:
                await message.answer("❌ Формат: <code>!setme 🔥</code>", parse_mode="HTML")
                return
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
            logger.error(f"[ECONOMY ERROR] cmd_setme: {e}")

    @dp.message(lambda m: m.text and m.text.lower().strip() == "!changeme")
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
            logger.error(f"[ECONOMY ERROR] cmd_changeme: {e}")

    # 9. АДМИН: ПОПОЛНИТЬ
    @dp.message(lambda m: m.text and m.text.lower().strip().startswith("+пополнить карман"))
    async def cmd_admin_add(message: Message):
        try:
            if not is_admin(message.from_user.id):
                await message.answer("❌ Только для админов!")
                return
            parts = message.text.strip().split()
            target_user = message.reply_to_message.from_user if (
                        message.reply_to_message and message.reply_to_message.from_user) else None
            amount = None

            if target_user and len(parts) >= 2:
                amount = int(parts[1])
            elif len(parts) == 3:
                amount = int(parts[2])
                target_user = message.from_user
            else:
                await message.answer("❌ Формат: ответь на сообщение и напиши <code>+пополнить карман 500</code>",
                                     parse_mode="HTML")
                return

            data = load_data()
            user = get_or_create_user(data, target_user.id, target_user.username)
            user["coins"] = user.get("coins", 0) + amount
            save_data(data)

            target_name = get_name_by_id(data, target_user.id, target_user.username)
            await message.answer(
                f"💰 <b>Карман пополнен!</b>\n\n👤 Кому: {target_name}\n➕ Начислено: <b>{amount}</b> coin 🪙\n📊 Баланс: <b>{user['coins']}</b> coin 🪙",
                parse_mode="HTML")
        except ValueError:
            await message.answer("❌ Сумма должна быть числом!")
        except Exception as e:
            logger.error(f"[ECONOMY ERROR] cmd_admin_add: {e}")

    # 10. ТЕГ
    @dp.message(lambda m: m.text and m.text.lower().strip() == "!тег")
    async def cmd_tag(message: Message):
        await message.answer(f"👋 Я на месте, {safe_text(message.from_user.full_name)}!")