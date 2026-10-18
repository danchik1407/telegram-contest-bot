import asyncio
import random
import time
import html as html_module
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus

from services.economy import load_data, save_data, get_or_create_user, format_time
from config import ADMIN_IDS

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
    @dp.message(F.text.regexp(r'(?i)^(!помощь|!команды|!help)$'))
    async def cmd_help(message: Message):
        help_text = (
            "📖 <b>СПИСОК КОМАНД БОТА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 <b>Сундуки:</b>\n"
            "• <code>!открыть</code> — открыть сундук (КД 5 часов)\n\n"
            "💰 <b>Экономика:</b>\n"
            "• <code>!посмотреть карман</code> — твой баланс\n"
            "• <code>!посмотреть карман @username</code> — баланс другого\n"
            "• <code>!перевод @username сумма</code> — перевести коины\n"
            "• <code>!топ монет</code> — топ-10 богачей\n\n"
            "🎲 <b>Игры:</b>\n"
            "• <code>!кубы @username ставка</code> — дуэль в кости\n"
            "• Ответь на сообщение + <code>!кубы ставка</code> — быстрый вызов\n\n"
            "📢 <b>Созывы:</b>\n"
            "• <code>!all [текст]</code> — массовый созыв\n"
            "• <code>!admins [текст]</code> — созыв админов\n"
            "• <code>!stop</code> — остановить созыв\n"
            "• <code>!me</code> / <code>!setme эмодзи</code> / <code>!changeme</code> — позывной\n\n"
            "🔧 <b>Системные:</b>\n"
            "• <code>!тег</code> — проверка бота"
        )
        await message.answer(help_text, parse_mode="HTML")

    async def summon_all_members(chat_id: int, call_text: str, starter_id: int):
        active_summons[chat_id] = True
        try:
            data = load_data()
            users_to_tag = [int(uid_str) for uid_str in data["users"].keys() if int(uid_str) != starter_id]
            random.shuffle(users_to_tag)

            if not users_to_tag:
                await bot.send_message(chat_id, "❌ Некого созывать. Пользователи должны хотя бы раз написать боту.")
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
            await bot.send_message(chat_id, f"❌ Ошибка при созыве: {e}")
        finally:
            if chat_id in active_summons:
                del active_summons[chat_id]

    @dp.message(F.text.regexp(r'(?i)^(!all|!каллалл|!алл|!callall)(\s+.*)?$'))
    async def cmd_all(message: Message):
        if message.chat.type not in ["group", "supergroup"]:
            await message.answer("❌ Эта команда работает только в групповых чатах!")
            return
        user_id = message.from_user.id
        if not is_admin(user_id) and not await is_chat_admin(bot, user_id, message.chat.id):
            await message.answer("❌ Команда недоступна (только для админов чата или бота)")
            return

        parts = message.text.strip().split()
        call_text = " ".join(parts[1:]) if len(parts) > 1 else "📢 Общий сбор всех участников!"
        await message.answer(
            f"🔄 Начинаю массовый созыв...\nТекст: {safe_text(call_text)}\n\n⚠️ Для остановки напишите: <code>!stop</code>",
            parse_mode="HTML")
        asyncio.create_task(summon_all_members(message.chat.id, call_text, user_id))

    @dp.message(F.text.regexp(r'(?i)^(!stop|!стоп|!остановить|!отмена|!стой)$'))
    async def cmd_stop(message: Message):
        if active_summons.get(message.chat.id, False):
            active_summons[message.chat.id] = False
            await message.answer("⏹️ Команда остановки принята. Созыв прекратится после текущего сообщения.")
        else:
            await message.answer("❌ Активных массовых созывов в этом чате нет.")

    @dp.message(F.text.regexp(r'(?i)^(!admins|!калладминс|!админы)(\s+.*)?$'))
    async def cmd_admins(message: Message):
        if message.chat.type not in ["group", "supergroup"]:
            await message.answer("❌ Эта команда работает только в групповых чатах!")
            return
        parts = message.text.strip().split()
        call_text = " ".join(parts[1:]) if len(parts) > 1 else "📢 Сбор администраторов!"
        try:
            members = await bot.get_chat_administrators(chat_id=message.chat.id)
            admins_to_tag = [m.user for m in members if not m.user.is_bot]
            if not admins_to_tag:
                await message.answer("❌ Администраторы не найдены.")
                return
            mentions = [f"[{u.full_name[:20]}](tg://user?id={u.id})" for u in admins_to_tag]
            await message.answer(f"📢 {call_text}\n\n" + ", ".join(mentions), parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

    @dp.message(F.text.regexp(r'(?i)^(!me|!ми|!позывной)$'))
    async def cmd_me(message: Message):
        data = load_data()
        user = get_or_create_user(data, message.from_user.id, message.from_user.username)
        call_sign = user.get("call_sign")
        name = message.from_user.full_name
        if call_sign:
            await message.answer(f"📛 Твой позывной: {call_sign}\n👤 Имя: {safe_text(name)}")
        else:
            await message.answer(f"👤 Имя: {safe_text(name)}\n💡 Установи позывной командой: <code>!setme 🔥</code>",
                                 parse_mode="HTML")

    @dp.message(F.text.regexp(r'(?i)^!setme\s+(.+)$'))
    async def cmd_setme(message: Message):
        parts = message.text.strip().split()
        emoji = parts[1]
        if len(emoji) > 8:
            await message.answer("❌ Позывной должен быть коротким (до 8 символов).")
            return
        data = load_data()
        user = get_or_create_user(data, message.from_user.id, message.from_user.username)
        user["call_sign"] = emoji
        save_data(data)
        await message.answer(f"✅ Твой новый позывной: {emoji}")

    @dp.message(F.text.regexp(r'(?i)^(!changeme|!чанджми)$'))
    async def cmd_changeme(message: Message):
        emojis = ["🔥", "💎", "🐺", "🦊", "🐻", "🦁", "🐯", "🐲", "👻", "🤖", "👽", "🎯", "💀", "👑", "🎭", "🦅", "🦈", "🐍"]
        emoji = random.choice(emojis)
        data = load_data()
        user = get_or_create_user(data, message.from_user.id, message.from_user.username)
        user["call_sign"] = emoji
        save_data(data)
        await message.answer(f"✅ Твой новый случайный позывной: {emoji}")

    @dp.message(F.text.regexp(r'(?i)^!перевод(\s+.*)?$'))
    async def cmd_transfer(message: Message):
        data = load_data()
        sender = get_or_create_user(data, message.from_user.id, message.from_user.username)
        target_user, amount = None, None

        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            parts = message.text.strip().split()
            if len(parts) < 2:
                await message.answer("❌ Укажи сумму: <code>!перевод 50</code>", parse_mode="HTML")
                return
            try:
                amount = int(parts[1])
            except ValueError:
                await message.answer("❌ Сумма должна быть числом.")
                return
        else:
            parts = message.text.strip().split()
            if len(parts) < 3:
                await message.answer("❌ Формат: <code>!перевод @username 50</code>", parse_mode="HTML")
                return
            username_arg = parts[1].lstrip("@").lower()
            try:
                amount = int(parts[2])
            except ValueError:
                await message.answer("❌ Сумма должна быть числом.")
                return

            for uid_str, udata in data["users"].items():
                if udata.get("username", "").lower() == username_arg:
                    target_user = type('User', (), {'id': int(uid_str), 'username': udata.get("username")})()
                    break
            if not target_user:
                await message.answer("❌ Пользователь не найден. Он должен хотя бы раз написать боту.")
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

    @dp.message(F.text.regexp(r'(?i)^!кубы(\s+.*)?$'))
    async def cmd_dice_challenge(message: Message):
        parts = message.text.strip().split()
        target_user, amount = None, None

        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
            if len(parts) < 2:
                await message.answer("🎲 Формат: <code>!кубы ставка</code> (ответом на сообщение)", parse_mode="HTML")
                return
            try:
                amount = int(parts[1])
            except ValueError:
                await message.answer("❌ Ставка должна быть числом.")
                return
        else:
            if len(parts) < 3:
                await message.answer("🎲 Формат: <code>!кубы @username ставка</code>", parse_mode="HTML")
                return
            username_arg = parts[1].lstrip("@").lower()
            try:
                amount = int(parts[2])
            except ValueError:
                await message.answer("❌ Ставка должна быть числом.")
                return

            data = load_data()
            for uid_str, udata in data["users"].items():
                if udata.get("username", "").lower() == username_arg:
                    target_user = type('User', (), {'id': int(uid_str), 'username': udata.get("username")})()
                    break
            if not target_user:
                await message.answer("❌ Пользователь не найден.")
                return

        if amount <= 0:
            await message.answer("❌ Ставка должна быть больше 0.")
            return

        data = load_data()
        challenger = get_or_create_user(data, message.from_user.id, message.from_user.username)

        if target_user.id == message.from_user.id:
            await message.answer("❌ Нельзя играть сам с собой 😄")
            return
        if challenger["coins"] < amount:
            await message.answer(f"❌ У тебя недостаточно коинов.\nНужно: <b>{amount}</b> 🪙", parse_mode="HTML")
            return

        challenged = get_or_create_user(data, target_user.id, target_user.username)
        if challenged["coins"] < amount:
            await message.answer(
                f"❌ У {get_name_by_id(data, target_user.id, target_user.username)} недостаточно коинов.",
                parse_mode="HTML")
            return

        challenge_id = f"{message.from_user.id}_{target_user.id}_{int(time.time())}"
        active_challenges[challenge_id] = {
            "challenger_id": message.from_user.id,
            "challenger_username": message.from_user.username,
            "challenged_id": target_user.id,
            "challenged_username": target_user.username,
            "amount": amount,
            "chat_id": message.chat.id,
            "message_id": None
        }

        challenger_name = get_name_by_id(data, message.from_user.id, message.from_user.username)
        challenged_name = get_name_by_id(data, target_user.id, target_user.username)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Принять", callback_data=f"dice_accept_{challenge_id}"),
            InlineKeyboardButton(text="❌ Отказ", callback_data=f"dice_decline_{challenge_id}")
        ]])

        sent_msg = await message.answer(
            f"🎲 <b>ВЫЗОВ НА ДУЭЛЬ!</b>\n\n👤 {challenger_name} вызывает {challenged_name}\n💰 Ставка: <b>{amount}</b> coin 🪙\n🎯 Победитель забирает: <b>{amount * 2}</b> coin 🪙\n\n⏳ Время на ответ: {CHALLENGE_TIMEOUT} секунд",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        active_challenges[challenge_id]["message_id"] = sent_msg.message_id

        async def check_timeout():
            await asyncio.sleep(CHALLENGE_TIMEOUT)
            if challenge_id in active_challenges:
                try:
                    await sent_msg.edit_text(
                        f"⏰ <b>Вызов отменён</b> (время вышло)\n\n{challenged_name} не успел ответить.",
                        parse_mode="HTML")
                except Exception:
                    pass
                del active_challenges[challenge_id]

        asyncio.create_task(check_timeout())

    @dp.callback_query(F.data.startswith("dice_accept_"))
    async def cb_dice_accept(callback: CallbackQuery):
        challenge_id = callback.data.replace("dice_accept_", "")
        if challenge_id not in active_challenges:
            await callback.answer("⏰ Этот вызов уже неактуален.", show_alert=True)
            return
        challenge = active_challenges[challenge_id]
        if callback.from_user.id != challenge["challenged_id"]:
            await callback.answer("❌ Этот вызов не для тебя!", show_alert=True)
            return

        await callback.answer("🎲 Бросаем кубики...")
        data = load_data()
        challenger = get_or_create_user(data, challenge["challenger_id"], challenge.get("challenger_username"))
        challenged = get_or_create_user(data, challenge["challenged_id"], callback.from_user.username)
        amount = challenge["amount"]
        chat_id = challenge["chat_id"]

        challenger["coins"] -= amount
        challenged["coins"] -= amount
        save_data(data)

        challenger_name = get_name_by_id(data, challenge["challenger_id"], challenge.get("challenger_username"))
        challenged_name = get_name_by_id(data, challenge["challenged_id"], callback.from_user.username)

        try:
            await callback.message.edit_text(f"🎲 <b>Дуэль началась!</b>", parse_mode="HTML")
        except Exception:
            pass

        queue_msg = await callback.message.answer(f"🎲 <b>Бросает</b> {challenger_name}...", parse_mode="HTML")
        dice1_msg = await bot.send_dice(chat_id=chat_id, emoji="🎲")
        dice1_value = dice1_msg.dice.value
        await asyncio.sleep(1.5)

        try:
            await queue_msg.edit_text(f"🎲 <b>Теперь бросает</b> {challenged_name}...", parse_mode="HTML")
        except Exception:
            pass

        dice2_msg = await bot.send_dice(chat_id=chat_id, emoji="🎲")
        dice2_value = dice2_msg.dice.value
        await asyncio.sleep(1.5)

        if dice1_value > dice2_value:
            challenger["coins"] += amount * 2
            result_text = f"🎲 <b>РЕЗУЛЬТАТ ДУЭЛИ!</b>\n\n👑 {challenger_name} выбросил: <b>{dice1_value}</b> 🎲\n👤 {challenged_name} выбросил: <b>{dice2_value}</b> 🎲\n\n🏆 <b>Победил {challenger_name}!</b>\n💰 Выигрыш: <b>{amount * 2}</b> coin 🪙"
        elif dice2_value > dice1_value:
            challenged["coins"] += amount * 2
            result_text = f"🎲 <b>РЕЗУЛЬТАТ ДУЭЛИ!</b>\n\n👤 {challenger_name} выбросил: <b>{dice1_value}</b> 🎲\n👑 {challenged_name} выбросил: <b>{dice2_value}</b> 🎲\n\n🏆 <b>Победил {challenged_name}!</b>\n💰 Выигрыш: <b>{amount * 2}</b> coin 🪙"
        else:
            challenger["coins"] += amount
            challenged["coins"] += amount
            result_text = f"🎲 <b>РЕЗУЛЬТАТ ДУЭЛИ!</b>\n\n👤 {challenger_name} выбросил: <b>{dice1_value}</b> 🎲\n👤 {challenged_name} выбросил: <b>{dice2_value}</b> 🎲\n\n🤝 <b>Ничья!</b> Ставки возвращены."

        save_data(data)
        del active_challenges[challenge_id]

        for msg_id in [dice1_msg.message_id, dice2_msg.message_id, queue_msg.message_id]:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass

        await callback.message.answer(result_text, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("dice_decline_"))
    async def cb_dice_decline(callback: CallbackQuery):
        challenge_id = callback.data.replace("dice_decline_", "")
        if challenge_id not in active_challenges:
            await callback.answer("⏰ Этот вызов уже неактуален.", show_alert=True)
            return
        challenge = active_challenges[challenge_id]
        if callback.from_user.id != challenge["challenged_id"]:
            await callback.answer("❌ Этот вызов не для тебя!", show_alert=True)
            return

        await callback.answer()
        decliner_name = callback.from_user.username or f"id{challenge['challenged_id']}"
        try:
            await callback.message.edit_text(
                f"🎲 <b>Вызов отклонён</b>\n\n👤 @{safe_text(decliner_name)} отказался от дуэли.", parse_mode="HTML")
        except Exception:
            pass
        del active_challenges[challenge_id]

    @dp.message(F.text.regexp(r'(?i)^!открыть$'))
    async def cmd_open(message: Message):
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
            await message.answer(f"🎁 <b>Сундук открыт!</b>\n\n🎉 Тебе выпало: <b>{reward}</b> coin 🪙", parse_mode="HTML")

    @dp.message(F.text.regexp(r'(?i)^!посмотреть карман(\s+.*)?$'))
    async def cmd_pocket(message: Message):
        data = load_data()
        target = message.reply_to_message.from_user if message.reply_to_message else None

        if not target and len(message.text.strip().split()) >= 3:
            username_arg = message.text.strip().split()[2].lstrip("@").lower()
            for uid_str, udata in data["users"].items():
                if udata.get("username", "").lower() == username_arg:
                    target = type('User', (), {'id': int(uid_str), 'username': udata.get("username")})()
                    break

        if not target:
            target = message.from_user

        user = get_or_create_user(data, target.id, target.username)
        display_name = f"@{target.username}" if target.username else f"id{target.id}"
        await message.answer(f"💰 <b>Карман {safe_text(display_name)}</b>\n\n{user.get('coins', 0)} coin 🪙",
                             parse_mode="HTML")

    @dp.message(F.text.regexp(r'(?i)^!топ монет$'))
    async def cmd_top_coins(message: Message):
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
            name = u['username'] if not str(u['username']).startswith("id") else u['username']
            msg += f"{prefix} {safe_text(name)} — <b>{u['coins']}</b> coin 🪙\n"
        await message.answer(msg, parse_mode="HTML")

    @dp.message(F.text.regexp(r'(?i)^\+пополнить карман(\s+.*)?$'))
    async def cmd_admin_add(message: Message):
        if not is_admin(message.from_user.id):
            await message.answer("❌ Команда недоступна")
            return

        parts = message.text.strip().split()
        target_user = message.reply_to_message.from_user if message.reply_to_message else None
        amount = None

        if target_user and len(parts) >= 2:
            try:
                amount = int(parts[1])
            except:
                await message.answer("❌ Укажи число.")
                return
        elif len(parts) == 3:
            try:
                amount = int(parts[2])
            except:
                await message.answer("❌ Укажи число.")
                return
        elif len(parts) == 4:
            username_arg = parts[2].lstrip("@").lower()
            try:
                amount = int(parts[3])
            except:
                await message.answer("❌ Укажи число.")
                return
            data = load_data()
            for uid_str, udata in data["users"].items():
                if udata.get("username", "").lower() == username_arg:
                    target_user = type('User', (), {'id': int(uid_str), 'username': udata.get("username")})()
                    break
            if not target_user:
                await message.answer("❌ Пользователь не найден.")
                return
        else:
            await message.answer("❌ Формат: <code>+пополнить карман 500</code> или ответом на сообщение",
                                 parse_mode="HTML")
            return

        if not target_user:
            target_user = message.from_user

        data = load_data()
        user = get_or_create_user(data, target_user.id, target_user.username)
        user["coins"] = user.get("coins", 0) + amount
        save_data(data)

        target_name = get_name_by_id(data, target_user.id, target_user.username)
        await message.answer(
            f"💰 <b>Карман пополнен!</b>\n\n👤 Кому: {target_name}\n➕ Начислено: <b>{amount}</b> coin 🪙\n📊 Баланс: <b>{user['coins']}</b> coin 🪙",
            parse_mode="HTML")

    @dp.message(F.text.regexp(r'(?i)^!тег$'))
    async def cmd_tag(message: Message):
        await message.answer(f"Пользователь {safe_text(message.from_user.full_name)} тегнул меня, я на месте 👍")