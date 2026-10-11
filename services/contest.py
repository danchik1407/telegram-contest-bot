import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ContestService:
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
        logger.info("Конкурс остановлен")

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
            logger.debug("Таймер отменён")
        except Exception as e:
            logger.error(f"Ошибка таймера: {e}")