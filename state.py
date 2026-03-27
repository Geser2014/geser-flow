"""
Синглтон состояния приложения.
Хранит текущую сессию, статус, таймеры.
"""

from datetime import datetime


class AppState:
    """Единственный экземпляр состояния приложения."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self):
        self.session_id: int | None = None
        self.project_name: str = ""
        self.status: str = "idle"  # idle | working | paused | on_break
        self.session_start: datetime | None = None
        self.work_seconds: int = 0
        self.pause_start: datetime | None = None
        self.pause_id: int | None = None
        self.last_check_time: datetime | None = None
        # Счётчик непрерывной работы для перекуров (в секундах)
        self.continuous_work_seconds: int = 0

    def reset(self):
        """Сброс состояния к idle."""
        self._init_state()

    @property
    def is_active(self) -> bool:
        return self.status in ("working", "paused", "on_break")
