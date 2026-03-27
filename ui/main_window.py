"""
Главное окно приложения.
Два режима: idle (выбор проекта) и working (таймер).
"""

import customtkinter as ctk
from state import AppState
from db import (
    get_projects, start_session, end_session, start_pause, end_pause,
    get_stats_today,
)
import config


# Цвета
BG_MAIN = "#1a1a1a"
BG_CARD = "#242424"
TEXT = "#e0e0e0"
ACCENT = "#3d8ef0"
GREEN = "#4caf50"
YELLOW = "#ff9800"
RED = "#f44336"
MUTED = "#888888"


class MainWindow(ctk.CTkToplevel):
    def __init__(self, master, on_open_dashboard=None, on_open_settings=None):
        super().__init__(master)
        self.title("Geser Flow")
        self.geometry("300x400")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)

        self.app_state = AppState()
        self._on_open_dashboard = on_open_dashboard
        self._on_open_settings = on_open_settings
        self._timer_job = None
        self._pause_seconds_display = 0

        # Перехват закрытия — скрываем в трей
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self._build_ui()
        self._render_state()

    def _build_ui(self):
        """Строит все виджеты (оба режима)."""
        # Верхняя панель с кнопками
        top_bar = ctk.CTkFrame(self, fg_color="transparent", height=40)
        top_bar.pack(fill="x", padx=10, pady=(10, 0))
        top_bar.pack_propagate(False)

        # Спейсер слева
        ctk.CTkLabel(top_bar, text="", fg_color="transparent").pack(side="left", expand=True)

        self._btn_dashboard = ctk.CTkButton(
            top_bar, text="📊", width=36, height=36,
            fg_color=BG_CARD, hover_color="#333333",
            command=self._open_dashboard,
        )
        self._btn_dashboard.pack(side="right", padx=2)

        self._btn_settings = ctk.CTkButton(
            top_bar, text="⚙", width=36, height=36,
            fg_color=BG_CARD, hover_color="#333333",
            command=self._open_settings,
        )
        self._btn_settings.pack(side="right", padx=2)

        # Контейнер контента
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=20, pady=10)

        # === Виджеты для idle ===
        self._idle_frame = ctk.CTkFrame(self._content, fg_color="transparent")

        self._lbl_title = ctk.CTkLabel(
            self._idle_frame, text="Geser Flow",
            font=("Segoe UI", 22, "bold"), text_color=TEXT,
        )
        self._lbl_title.pack(pady=(40, 20))

        self._entry_project = ctk.CTkEntry(
            self._idle_frame, placeholder_text="Над чем работаешь?",
            width=240, height=38, fg_color=BG_CARD, text_color=TEXT,
            border_color=ACCENT,
        )
        self._entry_project.pack(pady=(0, 5))

        # Список автодополнения
        self._listbox_frame = ctk.CTkFrame(self._idle_frame, fg_color=BG_CARD, corner_radius=6)
        self._listbox_var = []
        self._suggestion_buttons: list[ctk.CTkButton] = []

        self._entry_project.bind("<KeyRelease>", self._on_entry_change)
        self._entry_project.bind("<Return>", lambda e: self._start_work())

        self._btn_start = ctk.CTkButton(
            self._idle_frame, text="▶  Начать работу",
            width=240, height=44, font=("Segoe UI", 15, "bold"),
            fg_color=ACCENT, hover_color="#2d6ed0",
            command=self._start_work,
        )
        self._btn_start.pack(pady=(15, 0))

        # === Виджеты для working/paused ===
        self._work_frame = ctk.CTkFrame(self._content, fg_color="transparent")

        self._lbl_project = ctk.CTkLabel(
            self._work_frame, text="", font=("Segoe UI", 12),
            text_color=MUTED,
        )
        self._lbl_project.pack(pady=(20, 5))

        # Индикатор статуса
        self._indicator = ctk.CTkFrame(
            self._work_frame, width=12, height=12,
            corner_radius=6, fg_color=GREEN,
        )
        self._indicator.pack(pady=(0, 10))

        self._lbl_timer = ctk.CTkLabel(
            self._work_frame, text="00:00:00",
            font=("Consolas", 36, "bold"), text_color=TEXT,
        )
        self._lbl_timer.pack(pady=(0, 5))

        self._lbl_pause_info = ctk.CTkLabel(
            self._work_frame, text="",
            font=("Segoe UI", 13), text_color=YELLOW,
        )
        self._lbl_pause_info.pack(pady=(0, 10))

        # Кнопка продолжить (видна только при паузе)
        self._btn_resume = ctk.CTkButton(
            self._work_frame, text="▶  Продолжить работу",
            width=240, height=40, font=("Segoe UI", 14),
            fg_color=GREEN, hover_color="#388e3c",
            command=self._resume_work,
        )

        self._btn_stop = ctk.CTkButton(
            self._work_frame, text="■  Завершить сессию",
            width=240, height=44, font=("Segoe UI", 15, "bold"),
            fg_color=RED, hover_color="#c62828",
            command=self._stop_work,
        )
        self._btn_stop.pack(pady=(10, 0))

    def _render_state(self):
        """Показывает нужный набор виджетов по текущему статусу."""
        if self.app_state.status == "idle":
            self._work_frame.pack_forget()
            self._idle_frame.pack(fill="both", expand=True)
            self._btn_resume.pack_forget()
            self._lbl_pause_info.configure(text="")
            self._stop_timer()
        else:
            self._idle_frame.pack_forget()
            self._work_frame.pack(fill="both", expand=True)
            self._lbl_project.configure(text=self.app_state.project_name)
            self._update_indicator()
            if self.app_state.status in ("paused", "on_break"):
                self._btn_resume.pack(pady=(10, 0), before=self._btn_stop)
            else:
                self._btn_resume.pack_forget()
            self._start_timer()

    def _update_indicator(self):
        """Обновляет цвет индикатора."""
        colors = {"working": GREEN, "paused": YELLOW, "on_break": RED}
        self._indicator.configure(fg_color=colors.get(self.app_state.status, GREEN))

    # --- Таймер ---

    def _start_timer(self):
        """Запускает обновление таймера каждую секунду."""
        if self._timer_job is not None:
            return
        self._tick()

    def _stop_timer(self):
        if self._timer_job is not None:
            self.after_cancel(self._timer_job)
            self._timer_job = None

    def _tick(self):
        """Один тик таймера — раз в секунду."""
        if self.app_state.status == "working":
            self.app_state.work_seconds += 1
            self.app_state.continuous_work_seconds += 1
            self._lbl_pause_info.configure(text="")
        elif self.app_state.status in ("paused", "on_break"):
            self._pause_seconds_display += 1
            label = "Пауза" if self.app_state.status == "paused" else "Перерыв"
            m, s = divmod(self._pause_seconds_display, 60)
            self._lbl_pause_info.configure(text=f"{label}: {m:02d}:{s:02d}")

        # Обновляем отображение чистого рабочего времени
        h, rem = divmod(self.app_state.work_seconds, 3600)
        m, s = divmod(rem, 60)
        self._lbl_timer.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

        self._timer_job = self.after(1000, self._tick)

    # --- Автодополнение ---

    def _on_entry_change(self, event=None):
        """Показывает подсказки при вводе имени проекта."""
        text = self._entry_project.get().strip().lower()
        # Убираем старые подсказки
        self._listbox_frame.pack_forget()
        for btn in self._suggestion_buttons:
            btn.destroy()
        self._suggestion_buttons.clear()

        if not text:
            return

        projects = get_projects()
        matches = [p for p in projects if text in p.lower()][:5]
        if not matches:
            return

        self._listbox_frame.pack(pady=(0, 5), fill="x")
        for name in matches:
            btn = ctk.CTkButton(
                self._listbox_frame, text=name, anchor="w",
                fg_color="transparent", hover_color="#333333",
                text_color=TEXT, height=28,
                command=lambda n=name: self._select_project(n),
            )
            btn.pack(fill="x", padx=4, pady=1)
            self._suggestion_buttons.append(btn)

    def _select_project(self, name: str):
        """Выбирает проект из подсказок."""
        self._entry_project.delete(0, "end")
        self._entry_project.insert(0, name)
        self._listbox_frame.pack_forget()
        for btn in self._suggestion_buttons:
            btn.destroy()
        self._suggestion_buttons.clear()

    # --- Действия ---

    def _start_work(self):
        """Начинает рабочую сессию."""
        name = self._entry_project.get().strip()
        if not name:
            self._entry_project.configure(border_color=RED)
            self.after(1500, lambda: self._entry_project.configure(border_color=ACCENT))
            return

        session_id = start_session(name)
        self.app_state.session_id = session_id
        self.app_state.project_name = name
        self.app_state.status = "working"
        self.app_state.work_seconds = 0
        self.app_state.continuous_work_seconds = 0
        self._pause_seconds_display = 0

        from datetime import datetime
        self.app_state.session_start = datetime.now()
        self.app_state.last_check_time = datetime.now()

        self._render_state()

    def _stop_work(self):
        """Завершает текущую сессию."""
        if self.app_state.session_id is None:
            return

        # Закрываем открытую паузу если есть
        if self.app_state.pause_id is not None:
            end_pause(self.app_state.pause_id)

        # Подсчёт суммарных пауз и перекуров
        pause_sec = 0
        break_sec = 0
        if self.app_state.session_start:
            from datetime import datetime
            total_elapsed = int((datetime.now() - self.app_state.session_start).total_seconds())
            non_work = total_elapsed - self.app_state.work_seconds
            # Грубое разделение — пишем всё как pause_sec, break_sec отдельно не считаем тут
            pause_sec = max(non_work, 0)

        end_session(self.app_state.session_id, self.app_state.work_seconds, pause_sec, break_sec)
        self.app_state.reset()
        self._entry_project.delete(0, "end")
        self._render_state()

    def _resume_work(self):
        """Возобновляет работу после паузы/перерыва."""
        if self.app_state.pause_id is not None:
            end_pause(self.app_state.pause_id)
            self.app_state.pause_id = None

        self.app_state.status = "working"
        self.app_state.pause_start = None
        self._pause_seconds_display = 0
        from datetime import datetime
        self.app_state.last_check_time = datetime.now()
        self._update_indicator()
        self._btn_resume.pack_forget()
        self._lbl_pause_info.configure(text="")

    def start_auto_pause(self):
        """Вызывается из popup_check при таймауте — автопауза."""
        if self.app_state.status != "working":
            return
        from datetime import datetime
        self.app_state.status = "paused"
        self.app_state.pause_start = datetime.now()
        self.app_state.pause_id = start_pause(self.app_state.session_id, "auto")
        self._pause_seconds_display = 0
        self._update_indicator()
        self._btn_resume.pack(pady=(10, 0), before=self._btn_stop)

    def start_break(self):
        """Вызывается из popup_break — начинает перерыв."""
        if self.app_state.status != "working":
            return
        from datetime import datetime
        self.app_state.status = "on_break"
        self.app_state.pause_start = datetime.now()
        self.app_state.pause_id = start_pause(self.app_state.session_id, "break")
        self.app_state.continuous_work_seconds = 0
        self._pause_seconds_display = 0
        self._update_indicator()
        self._btn_resume.pack(pady=(10, 0), before=self._btn_stop)

    def _open_dashboard(self):
        if self._on_open_dashboard:
            self._on_open_dashboard()

    def _open_settings(self):
        if self._on_open_settings:
            self._on_open_settings()

    def show_window(self):
        """Показывает окно и выводит на передний план."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide_window(self):
        """Скрывает окно в трей."""
        self.withdraw()
