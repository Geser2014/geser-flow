"""
Системный трей — иконка, контекстное меню, уведомления.
Работает в отдельном потоке, UI обновляет через app.after().
"""

import threading
from PIL import Image, ImageDraw, ImageFont
import pystray
from state import AppState
from db import get_stats_today


def _create_icon_image() -> Image.Image:
    """Генерирует иконку 64×64: тёмный скруглённый квадрат, белая G."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, 62, 62], radius=12, fill="#141614")
    try:
        font = ImageFont.truetype("segoeuib.ttf", 38)
    except OSError:
        try:
            font = ImageFont.truetype("arialbd.ttf", 38)
        except OSError:
            font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "G", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (64 - tw) / 2 - bbox[0]
    y = (64 - th) / 2 - bbox[1]
    draw.text((x, y), "G", fill="#e8e8e8", font=font)
    return img


def _fmt_hm(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}ч {m}м"


class TrayIcon:
    def __init__(self, app_root, on_show=None, on_start=None, on_stop=None, on_quit=None):
        """
        app_root — корневой CTk виджет (для app.after).
        Колбэки вызываются в UI-потоке через after(0, ...).
        """
        self._app = app_root
        self._on_show = on_show
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_quit = on_quit
        self._state = AppState()
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        """Запускает трей в фоновом потоке."""
        self._icon = pystray.Icon(
            "GeserFlow",
            _create_icon_image(),
            "Geser Flow",
            menu=self._build_menu(),
        )
        self._icon.on_activate = self._on_click  # Вызывается при одиночном клике (Windows: двойной)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        """Останавливает трей."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def notify(self, message: str):
        """Показывает уведомление в трее."""
        if self._icon:
            try:
                self._icon.notify(message, "Geser Flow")
            except Exception:
                pass

    def update_menu(self):
        """Пересоздаёт меню (обновляет статус)."""
        if self._icon:
            self._icon.menu = self._build_menu()
            try:
                self._icon.update_menu()
            except Exception:
                pass

    def _build_menu(self) -> pystray.Menu:
        stats = get_stats_today()
        today_str = _fmt_hm(stats.get("work_seconds", 0))

        is_active = self._state.is_active

        items = [
            pystray.MenuItem("Открыть", self._on_click, default=True),
        ]

        if is_active:
            items.append(pystray.MenuItem("Завершить сессию", self._do_stop))
        else:
            items.append(pystray.MenuItem("Начать работу", self._do_start))

        items.append(pystray.MenuItem(f"Сегодня: {today_str}", None, enabled=False))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Выход", self._do_quit))

        return pystray.Menu(*items)

    def _on_click(self, icon=None, item=None):
        """Клик по иконке — показать окно."""
        if self._on_show:
            self._app.after(0, self._on_show)

    def _do_start(self, icon=None, item=None):
        if self._on_start:
            self._app.after(0, self._on_start)

    def _do_stop(self, icon=None, item=None):
        if self._on_stop:
            self._app.after(0, self._on_stop)

    def _do_quit(self, icon=None, item=None):
        if self._on_quit:
            self._app.after(0, self._on_quit)
