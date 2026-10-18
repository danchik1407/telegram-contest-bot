import os
import json
import time
from typing import Dict, Any, Optional

DATA_FILE = "data.json"

def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {"users": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {"users": {}}
            return json.loads(content)
    except Exception as e:
        print(f"[ECONOMY ERROR] Ошибка чтения data.json: {e}")
        return {"users": {}}

def save_data(data: Dict[str, Any]):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ECONOMY ERROR] Ошибка сохранения data.json: {e}")

def get_or_create_user(data: Dict[str, Any], user_id: int, username: Optional[str]) -> Dict[str, Any]:
    uid_str = str(user_id)
    if uid_str not in data["users"]:
        data["users"][uid_str] = {
            "coins": 0,
            "username": username or f"id{user_id}",
            "last_chest": 0,
            "last_call": 0,
            "call_sign": None
        }
    else:
        u = data["users"][uid_str]
        if username:
            u["username"] = username
        u.setdefault("last_chest", 0)
        u.setdefault("last_call", 0)
        u.setdefault("call_sign", None)
    return data["users"][uid_str]

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"