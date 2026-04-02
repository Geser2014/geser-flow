"""
Главный контроллер приложения.
Единственный экземпляр (lock-файл), жизненный цикл, проверки активности.
"""

import os
import sys
import tempfile
import customtkinter as ctk
from datetime import datetime

_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")

import config
from db import init_db, get_interrupted_session, mark_interrupted, end_session, delete_session
from state import AppState
from tray import TrayIcon
from ui.main_window import MainWindow
from ui.popup_check import PopupCheck
from ui.popup_break import PopupBreak
from ui.dashboard_window import DashboardWindow
from ui.settings_window import SettingsWindow


_LOCK_FILE = os.path.join(tempfile.gettempdir(), "geserflow.lock")


def _is_running() -> bool:
    """Проверяет, запущен ли уже экземпляр (по PID в lock-файле)."""
    if not os.path.exists(_LOCK_FILE):
        return False
    try:
        with open(_LOCK_FILE, "r") as f:
            pid = int(f.read().strip())
        # Проверяем жив ли процесс
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            kernel32.CloseHandle(handle)
            return True
        else:
            # Процесс мёртв — удаляем stale lock
            os.remove(_LOCK_FILE)
            return False
    except (ValueError, OSError):
        try:
            os.remove(_LOCK_FILE)
        except OSError:
            pass
        return False


def _create_lock():
    with open(_LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def _remove_lock():
    try:
        os.remove(_LOCK_FILE)
    except OSError:
        pass


class App:
    def __init__(self):
        if _is_running():
            # Попробуем показать уже запущенное окно, иначе просто выходим
            sys.exit(0)

        _create_lock()

        # Инициализация БД
        init_db()

        # Настройки customtkinter
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._root = ctk.CTk()
        self._root.withdraw()  # Скрываем корневое окно — используем Toplevel
        if os.path.exists(_ICON_PATH):
            self._root.iconbitmap(_ICON_PATH)

        self._state = AppState()
        self._main_window: MainWindow | None = None
        self._dashboard: DashboardWindow | None = None
        self._settings: SettingsWindow | None = None
        self._popup_check: PopupCheck | None = None
        self._popup_break: PopupBreak | None = None
        self._check_job = None
        self._break_timer_job = None

        # Трей
        self._tray = TrayIcon(
            self._root,
            on_show=self._show_main,
            on_start=self._tray_start,
            on_stop=self._tray_stop,
            on_quit=self._quit,
        )

        # Создаём главное окно
        self._main_window = MainWindow(
            self._root,
            on_open_dashboard=self._open_dashboard,
            on_open_settings=self._open_settings,
        )

        # Проверяем незавершённую сессию
        self._check_interrupted()

        # Запускаем трей
        self._tray.start()

        # Запускаем проверку активности
        self._schedule_check()
        self._schedule_break_check()

        # Перехват закрытия корневого окна
        self._root.protocol("WM_DELETE_WINDOW", self._quit)

    def run(self):
        try:
            self._root.mainloop()
        finally:
            _remove_lock()

    # --- Незавершённая сессия ---

    def _check_interrupted(self):
        """Показывает диалог если есть незавершённая сессия."""
        session = get_interrupted_session()
        if session is None:
            return

        dialog = ctk.CTkToplevel(self._root)
        dialog.title("Незавершённая сессия")
        dialog.geometry("380x160")
        dialog.resizable(False, False)
        dialog.configure(fg_color="#1a1a1a")
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        project = session["project_name"]
        stage = session.get("stage_name", "")
        start = session["start_time"]
        sid = session["id"]

        display = f'"{project}"'
        if stage and stage != "Общее":
            display += f" → {stage}"

        ctk.CTkLabel(
            dialog,
            text=f'Найдена незавершённая сессия:\n{display}, начата в {start}.\nЗавершить её?',
            font=("Segoe UI", 13), text_color="#e0e0e0",
            wraplength=340, justify="center",
        ).pack(pady=(18, 12))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        def finish():
            work_sec = session.get("work_seconds", 0)
            end_session(sid, work_sec, 0, 0)
            dialog.destroy()

        def delete():
            delete_session(sid)
            dialog.destroy()

        ctk.CTkButton(
            btn_frame, text="Завершить", width=120, height=36,
            fg_color="#3d8ef0", hover_color="#2d6ed0",
            command=finish,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="Удалить", width=120, height=36,
            fg_color="#f44336", hover_color="#c62828",
            command=delete,
        ).pack(side="left", padx=8)

    # --- Проверка активности ---

    def _schedule_check(self):
        """Планирует следующую проверку активности."""
        interval_ms = config.get("check_interval_min") * 60 * 1000
        self._check_job = self._root.after(interval_ms, self._do_check)

    def _do_check(self):
        """Показывает popup проверки если идёт работа."""
        if self._state.status == "working":
            self._show_check_popup()
        self._schedule_check()

    def _show_check_popup(self):
        if self._popup_check is not None:
            try:
                self._popup_check.destroy()
            except Exception:
                pass

        self._popup_check = PopupCheck(
            self._root,
            on_yes=self._check_yes,
            on_no=self._check_no,
            on_timeout=self._check_timeout,
        )

    def _check_yes(self):
        """Пользователь подтвердил — продолжаем."""
        self._state.last_check_time = datetime.now()
        self._popup_check = None
        self._tray.update_menu()

    def _check_no(self):
        """Пользователь нажал «Нет» — ставим паузу."""
        self._popup_check = None
        if self._main_window:
            self._main_window.start_auto_pause()
        self._tray.update_menu()

    def _check_timeout(self):
        """Таймаут проверки — автопауза."""
        self._popup_check = None
        if self._main_window:
            self._main_window.start_auto_pause()
        self._tray.notify("Таймер приостановлен")
        self._tray.update_menu()

    # --- Проверка перекуров ---

    def _schedule_break_check(self):
        """Проверяет каждые 30 сек, не пора ли предложить перерыв."""
        self._break_timer_job = self._root.after(30_000, self._do_break_check)

    def _do_break_check(self):
        if (
            config.get("break_mode_enabled")
            and self._state.status == "working"
        ):
            threshold = config.get("break_work_interval_min") * 60
            if self._state.continuous_work_seconds >= threshold:
                self._show_break_popup()

        self._schedule_break_check()

    def _show_break_popup(self):
        if self._popup_break is not None:
            try:
                self._popup_break.destroy()
            except Exception:
                pass

        work_min = self._state.continuous_work_seconds // 60

        self._popup_break = PopupBreak(
            self._root,
            work_minutes=work_min,
            on_break=self._take_break,
            on_skip=self._skip_break,
        )

    def _take_break(self):
        """Пользователь решил отдохнуть."""
        self._popup_break = None
        if self._main_window:
            self._main_window.start_break()

        # Запускаем таймер окончания перерыва
        dur_ms = config.get("break_duration_min") * 60 * 1000
        self._root.after(dur_ms, self._break_ended)
        self._tray.update_menu()

    def _skip_break(self):
        """Пользователь пропустил перерыв — сбрасываем счётчик."""
        self._popup_break = None
        self._state.continuous_work_seconds = 0

    def _break_ended(self):
        """Время перерыва истекло."""
        if self._state.status == "on_break":
            self._tray.notify("Перерыв окончен, возвращайся!")

    # --- Навигация ---

    def _show_main(self):
        if self._main_window:
            self._main_window.show_window()

    def _open_dashboard(self):
        if self._dashboard is not None:
            try:
                if self._dashboard.winfo_exists():
                    self._dashboard.focus()
                    return
            except Exception:
                pass
            self._dashboard = None
        self._dashboard = DashboardWindow(self._root)
        self._dashboard.protocol("WM_DELETE_WINDOW", lambda: self._close_dashboard())
        self._dashboard.after(100, self._dashboard.lift)

    def _close_dashboard(self):
        if self._dashboard:
            self._dashboard.destroy()
            self._dashboard = None

    def _open_settings(self):
        if self._settings is not None:
            try:
                if self._settings.winfo_exists():
                    self._settings.focus()
                    return
            except Exception:
                pass
            self._settings = None
        self._settings = SettingsWindow(self._root)
        self._settings.protocol("WM_DELETE_WINDOW", lambda: self._close_settings())
        self._settings.after(100, self._settings.lift)

    def _close_settings(self):
        if self._settings:
            self._settings.destroy()
            self._settings = None

    # --- Трей колбэки ---

    def _tray_start(self):
        self._show_main()

    def _tray_stop(self):
        if self._main_window:
            self._main_window._stop_work()
        self._tray.update_menu()

    def _quit(self):
        """Полный выход из приложения."""
        # Если есть активная сессия — помечаем как interrupted
        if self._state.session_id is not None:
            mark_interrupted(self._state.session_id)

        self._tray.stop()

        if self._check_job:
            self._root.after_cancel(self._check_job)
        if self._break_timer_job:
            self._root.after_cancel(self._break_timer_job)

        _remove_lock()
        self._root.quit()
        self._root.destroy()
