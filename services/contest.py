import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ContestService:
    """Один экземпляр = один конкурс в одном чате."""

    def __init__(self, duration: int, update_interval: int):
        self.duration = duration
        self.update_interval = update_interval
        self.state: Dict[str, Any] = self._reset_state()
        self._update_task: Optional[asyncio.Task] = None

    def _reset_state(self) -> Dict[str, Any]:
        return {
            "active": False,
            "ended": False,
            "chat_id": None,
            "leader_id": None,
            "leader_username": None,
            "leader_message_id": None,
            "end_time": None,
            "bot_message_id": None,
            "start_message_id": None,
            "admins_allowed": True,
            "prize": "Сюрприз",
            "pending_duration": None,
        }

    @property
    def is_active(self) -> bool:
        return self.state["active"] and not self.state["ended"]

    def start(self, chat_id: int, duration: int, prize: str, admins_allowed: bool) -> None:
        self.state = self._reset_state()
        self.state["active"] = True
        self.state["chat_id"] = chat_id
        self.state["end_time"] = datetime.now() + timedelta(seconds=duration)
        self.state["admins_allowed"] = admins_allowed
        self.state["prize"] = prize
        self.duration = duration
        logger.info(f"Конкурс начат: чат={chat_id}, приз={prize}, админы={admins_allowed}")

    def stop(self) -> None:
        self.state["active"] = False
        self.state["ended"] = True
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
        logger.info(f"Конкурс остановлен в чате {self.state['chat_id']}")

    def set_leader(self, user_id: int, username: Optional[str], message_id: int) -> None:
        self.state["leader_id"] = user_id
        self.state["leader_username"] = username
        self.state["leader_message_id"] = message_id
        self.state["end_time"] = datetime.now() + timedelta(seconds=self.duration)

    def is_same_leader(self, user_id: int) -> bool:
        return self.state["leader_id"] == user_id

    def set_bot_message(self, message_id: int) -> None:
        self.state["bot_message_id"] = message_id

    def set_start_message(self, message_id: int) -> None:
        self.state["start_message_id"] = message_id

    def get_remaining_seconds(self) -> float:
        if not self.state["end_time"]:
            return 0
        return (self.state["end_time"] - datetime.now()).total_seconds()

    async def start_timer_task(self, callback) -> None:
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
        self._update_task = asyncio.create_task(self._timer_loop(callback))

    async def _timer_loop(self, callback) -> None:
        print(f"🔄 [TIMER_LOOP] Запущен цикл таймера для чата {self.state['chat_id']}")
        try:
            while self.is_active:
                remaining = self.get_remaining_seconds()
                if remaining <= 0:
                    break
                await callback(int(remaining))
                await asyncio.sleep(self.update_interval)
            if self.is_active:
                await callback(0, finished=True)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Ошибка таймера: {e}")


class ContestManager:
    """Управляет конкурсами во всех чатах."""

    def __init__(self, duration: int, update_interval: int):
        self.default_duration = duration
        self.default_update_interval = update_interval
        self._services: Dict[int, ContestService] = {}

    def get_service(self, chat_id: int) -> ContestService:
        """Получить (или создать) сервис для конкретного чата."""
        if chat_id not in self._services:
            self._services[chat_id] = ContestService(
                duration=self.default_duration,
                update_interval=self.default_update_interval
            )
        return self._services[chat_id]

    def has_active_contest(self, chat_id: int) -> bool:
        """Есть ли активный конкурс в этом чате."""
        if chat_id not in self._services:
            return False
        return self._services[chat_id].is_active

    def any_active_contest(self) -> bool:
        """Есть ли активный конкурс хоть в одном чате."""
        return any(s.is_active for s in self._services.values())

    def get_active_chat_id(self) -> Optional[int]:
        """Вернуть chat_id чата, где идёт конкурс (если есть)."""
        for chat_id, service in self._services.items():
            if service.is_active:
                return chat_id
        return None