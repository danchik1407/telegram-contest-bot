def format_time_left(seconds: int) -> str:
    if seconds <= 0:
        return "0 сек"
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m} мин {s} сек"
    return f"{s} сек"


def message_link(chat_id: int, message_id: int) -> str:
    if str(chat_id).startswith("-100"):
        real_id = str(chat_id)[4:]
        return f"https://t.me/c/{real_id}/{message_id}"
    elif str(chat_id).startswith("-"):
        real_id = str(chat_id)[1:]
        return f"https://t.me/c/{real_id}/{message_id}"
    return f"https://t.me/{chat_id}/{message_id}"