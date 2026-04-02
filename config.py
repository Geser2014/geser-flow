"""
Управление настройками приложения.
Загрузка/сохранение settings.json, доступ к параметрам.
"""

import json
import os

# Путь к файлу настроек рядом с config.py
_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

_DEFAULTS = {
    "check_interval_min": 15,
    "check_timeout_sec": 60,
    "break_mode_enabled": True,
    "break_work_interval_min": 90,
    "break_duration_min": 10,
    "autostart": False,
    "theme": "dark",
    "turbo_mode": False,
}


def _load() -> dict:
    """Загружает настройки из файла, мержит с дефолтами."""
    data = dict(_DEFAULTS)
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return data


def _save(data: dict) -> None:
    """Сохраняет настройки в файл."""
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# Глобальный словарь настроек — загружается один раз при импорте
settings: dict = _load()


def get(key: str):
    """Получить значение настройки."""
    return settings.get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:
    """Установить значение настройки и сохранить на диск."""
    settings[key] = value
    _save(settings)


def save_all() -> None:
    """Сохранить все текущие настройки на диск."""
    _save(settings)


def reset() -> None:
    """Сбросить настройки к дефолтным."""
    settings.clear()
    settings.update(_DEFAULTS)
    _save(settings)
