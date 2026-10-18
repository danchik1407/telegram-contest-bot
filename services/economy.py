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
            data = json.loads(content)
            if "users" not in data:
                data["users"] = {}
            return data
    except Exception:
        return {"users": {}}

def save_data(data: Dict[str, Any]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
        if "last_chest" not in u:
            u["last_chest"] = 0
        if "last_call" not in u:
            u["last_call"] = 0
        if "call_sign" not in u:
            u["call_sign"] = None
    return data["users"][uid_str]

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"