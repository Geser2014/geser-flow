"""
Главное окно приложения.
Два режима: idle (выбор проекта) и working (таймер).
"""

import os
import customtkinter as ctk
from state import AppState
from db import (
    get_projects_sorted, get_stages, get_or_create_project,
    get_last_session_info, start_session, end_session,
    start_pause, end_pause, get_stats_today, get_or_create_stage,
)
import config

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")


# Цвета — тёмная тема в стиле investment calculator
BG_MAIN = "#0d0f0d"
BG_CARD = "#141614"
BORDER = "#2a2e2a"
TEXT = "#e8e8e8"
ACCENT = "#2ec4a0"
ORANGE = "#e8a838"
GREEN = "#2ec4a0"
YELLOW = "#e8a838"
RED = "#e05545"
MUTED = "#8a8e8a"
HOVER = "#1c201c"


class MainWindow(ctk.CTkToplevel):
    def __init__(self, master, on_open_dashboard=None, on_open_settings=None):
        super().__init__(master)
        self.title("Geser Flow")
        self.geometry("320x420")
        self.resizable(False, False)
        self.configure(fg_color=BG_MAIN)
        if os.path.exists(_ICON_PATH):
            self.after(300, lambda: self.iconbitmap(_ICON_PATH))

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
        top_bar.pack(fill="x", padx=12, pady=(10, 0))
        top_bar.pack_propagate(False)

        # Спейсер слева
        ctk.CTkLabel(top_bar, text="", fg_color="transparent").pack(side="left", expand=True)

        self._btn_dashboard = ctk.CTkButton(
            top_bar, text="📊", width=34, height=34,
            fg_color=BG_CARD, hover_color=HOVER,
            border_width=1, border_color=BORDER,
            corner_radius=6,
            command=self._open_dashboard,
        )
        self._btn_dashboard.pack(side="right", padx=3)

        self._btn_settings = ctk.CTkButton(
            top_bar, text="⚙", width=34, height=34,
            fg_color=BG_CARD, hover_color=HOVER,
            border_width=1, border_color=BORDER,
            corner_radius=6,
            command=self._open_settings,
        )
        self._btn_settings.pack(side="right", padx=3)

        # Контейнер контента
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=16, pady=10)

        # === Виджеты для idle ===
        self._idle_frame = ctk.CTkFrame(self._content, fg_color="transparent")

        self._lbl_title = ctk.CTkLabel(
            self._idle_frame, text="GESER FLOW",
            font=("Segoe UI", 20, "bold"), text_color=TEXT,
        )
        self._lbl_title.pack(pady=(30, 4))

        self._lbl_subtitle = ctk.CTkLabel(
            self._idle_frame, text="учёт рабочего времени",
            font=("Segoe UI", 11), text_color=MUTED,
        )
        self._lbl_subtitle.pack(pady=(0, 24))

        # Карточка ввода проекта и этапа
        input_card = ctk.CTkFrame(
            self._idle_frame, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=8,
        )
        input_card.pack(fill="x", pady=(0, 5))

        # --- Project dropdown ---
        ctk.CTkLabel(
            input_card, text="ПРОЕКТ",
            font=("Segoe UI", 9), text_color=MUTED,
        ).pack(padx=14, pady=(10, 2), anchor="w")

        self._project_var = ctk.StringVar(value="")
        self._project_menu = ctk.CTkOptionMenu(
            input_card,
            variable=self._project_var,
            values=[],
            width=250, height=36,
            fg_color=BG_MAIN,
            text_color=TEXT,
            button_color=BORDER,
            button_hover_color=HOVER,
            dropdown_fg_color=BG_CARD,
            dropdown_text_color=TEXT,
            dropdown_hover_color=HOVER,
            command=self._on_project_selected,
        )
        self._project_menu.pack(padx=14, pady=(0, 6))

        self._new_project_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        self._entry_new_project = ctk.CTkEntry(
            self._new_project_frame, placeholder_text="Название проекта",
            width=206, height=32, fg_color=BG_MAIN, text_color=TEXT,
            border_color=BORDER, border_width=1,
            placeholder_text_color=MUTED,
        )
        self._entry_new_project.pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            self._new_project_frame, text="✓", width=36, height=32,
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=6,
            command=self._confirm_new_project,
        ).pack(side="left")

        # --- Stage dropdown ---
        ctk.CTkLabel(
            input_card, text="ЭТАП",
            font=("Segoe UI", 9), text_color=MUTED,
        ).pack(padx=14, pady=(4, 2), anchor="w")

        self._stage_var = ctk.StringVar(value="")
        self._stage_menu = ctk.CTkOptionMenu(
            input_card,
            variable=self._stage_var,
            values=[],
            width=250, height=36,
            fg_color=BG_MAIN,
            text_color=TEXT,
            button_color=BORDER,
            button_hover_color=HOVER,
            dropdown_fg_color=BG_CARD,
            dropdown_text_color=TEXT,
            dropdown_hover_color=HOVER,
            command=self._on_stage_selected,
        )
        self._stage_menu.pack(padx=14, pady=(0, 6))

        self._new_stage_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        self._entry_new_stage = ctk.CTkEntry(
            self._new_stage_frame, placeholder_text="Название этапа",
            width=206, height=32, fg_color=BG_MAIN, text_color=TEXT,
            border_color=BORDER, border_width=1,
            placeholder_text_color=MUTED,
        )
        self._entry_new_stage.pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            self._new_stage_frame, text="✓", width=36, height=32,
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=6,
            command=self._confirm_new_stage,
        ).pack(side="left")

        # Padding at bottom of card
        ctk.CTkLabel(input_card, text="", height=4, fg_color="transparent").pack()

        self._load_projects_dropdown()

        self._btn_start = ctk.CTkButton(
            self._idle_frame, text="▶  НАЧАТЬ РАБОТУ",
            width=260, height=44, font=("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=8,
            command=self._start_work,
        )
        self._btn_start.pack(pady=(16, 0))

        # Статистика за сегодня
        self._lbl_today = ctk.CTkLabel(
            self._idle_frame, text="",
            font=("Segoe UI", 11), text_color=MUTED,
        )
        self._lbl_today.pack(pady=(12, 0))
        self._update_today_label()

        # === Виджеты для working/paused ===
        self._work_frame = ctk.CTkFrame(self._content, fg_color="transparent")

        # Карточка с информацией о сессии
        session_card = ctk.CTkFrame(
            self._work_frame, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=8,
        )
        session_card.pack(fill="x", pady=(20, 10))

        ctk.CTkLabel(
            session_card, text="ТЕКУЩАЯ СЕССИЯ",
            font=("Segoe UI", 9), text_color=MUTED,
        ).pack(padx=14, pady=(10, 2), anchor="w")

        self._lbl_project = ctk.CTkLabel(
            session_card, text="", font=("Segoe UI", 13),
            text_color=TEXT,
        )
        self._lbl_project.pack(padx=14, pady=(0, 10), anchor="w")

        # Индикатор + таймер
        timer_frame = ctk.CTkFrame(self._work_frame, fg_color="transparent")
        timer_frame.pack(pady=(5, 0))

        self._indicator = ctk.CTkFrame(
            timer_frame, width=10, height=10,
            corner_radius=5, fg_color=GREEN,
        )
        self._indicator.pack(side="left", padx=(0, 10), pady=14)

        self._lbl_timer = ctk.CTkLabel(
            timer_frame, text="00:00:00",
            font=("Consolas", 38, "bold"), text_color=ORANGE,
        )
        self._lbl_timer.pack(side="left")

        self._lbl_pause_info = ctk.CTkLabel(
            self._work_frame, text="",
            font=("Segoe UI", 12), text_color=YELLOW,
        )
        self._lbl_pause_info.pack(pady=(4, 8))

        # Кнопка продолжить (видна только при паузе)
        self._btn_resume = ctk.CTkButton(
            self._work_frame, text="▶  ПРОДОЛЖИТЬ",
            width=260, height=40, font=("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=8,
            command=self._resume_work,
        )

        self._btn_stop = ctk.CTkButton(
            self._work_frame, text="■  ЗАВЕРШИТЬ",
            width=260, height=44, font=("Segoe UI", 14, "bold"),
            fg_color="transparent", hover_color="#2a1515",
            border_width=1, border_color=RED,
            text_color=RED, corner_radius=8,
            command=self._stop_work,
        )
        self._btn_stop.pack(pady=(6, 0))

    def _update_today_label(self):
        """Показывает статистику за сегодня."""
        stats = get_stats_today()
        sec = stats.get("work_seconds", 0)
        h, rem = divmod(sec, 3600)
        m = rem // 60
        if h > 0:
            self._lbl_today.configure(text=f"сегодня: {h}ч {m}м")
        elif m > 0:
            self._lbl_today.configure(text=f"сегодня: {m}м")
        else:
            self._lbl_today.configure(text="")

    # --- Dropdown logic ---

    def _load_projects_dropdown(self):
        """Loads projects into the project dropdown."""
        projects = get_projects_sorted()
        values = ["➕ Новый проект..."] + projects
        self._project_menu.configure(values=values)

        last = get_last_session_info()
        if last:
            last_project, last_stage = last
            if last_project in projects:
                self._project_var.set(last_project)
                self._load_stages_dropdown(last_project, default_stage=last_stage)
                return

        if projects:
            self._project_var.set(projects[0])
            self._load_stages_dropdown(projects[0])
        else:
            self._project_var.set("➕ Новый проект...")
            self._stage_menu.configure(values=[])
            self._stage_var.set("")

    def _load_stages_dropdown(self, project_name, default_stage=None):
        """Loads stages for a given project into the stage dropdown."""
        project_id = get_or_create_project(project_name)
        stages = get_stages(project_id)
        values = ["➕ Новый этап..."] + stages
        self._stage_menu.configure(values=values)

        if default_stage and default_stage in stages:
            self._stage_var.set(default_stage)
        elif stages:
            self._stage_var.set(stages[0])
        else:
            self._stage_var.set("➕ Новый этап...")

    def _on_project_selected(self, choice):
        """Called when user selects a project from the dropdown."""
        if choice == "➕ Новый проект...":
            self._new_project_frame.pack(padx=14, pady=(0, 6))
            self._entry_new_project.focus()
            self._stage_menu.configure(values=[])
            self._stage_var.set("")
        else:
            self._new_project_frame.pack_forget()
            self._load_stages_dropdown(choice)

    def _on_stage_selected(self, choice):
        """Called when user selects a stage from the dropdown."""
        if choice == "➕ Новый этап...":
            self._new_stage_frame.pack(padx=14, pady=(0, 6))
            self._entry_new_stage.focus()
        else:
            self._new_stage_frame.pack_forget()

    def _confirm_new_project(self):
        """Creates a new project and refreshes the dropdown."""
        name = self._entry_new_project.get().strip()
        if not name:
            return
        project_id = get_or_create_project(name)
        get_or_create_stage(project_id, "Общее")
        self._entry_new_project.delete(0, "end")
        self._new_project_frame.pack_forget()
        self._load_projects_dropdown()
        # Select the newly created project
        self._project_var.set(name)
        self._load_stages_dropdown(name)

    def _confirm_new_stage(self):
        """Creates a new stage under the current project and refreshes the dropdown."""
        stage_name = self._entry_new_stage.get().strip()
        if not stage_name:
            return
        project_name = self._project_var.get()
        if not project_name or project_name == "➕ Новый проект...":
            return
        project_id = get_or_create_project(project_name)
        get_or_create_stage(project_id, stage_name)
        self._entry_new_stage.delete(0, "end")
        self._new_stage_frame.pack_forget()
        self._load_stages_dropdown(project_name, default_stage=stage_name)

    # --- Render state ---

    def _render_state(self):
        """Показывает нужный набор виджетов по текущему статусу."""
        if self.app_state.status == "idle":
            self._work_frame.pack_forget()
            self._idle_frame.pack(fill="both", expand=True)
            self._btn_resume.pack_forget()
            self._lbl_pause_info.configure(text="")
            self._stop_timer()
            self._update_today_label()
            self._load_projects_dropdown()
        else:
            self._idle_frame.pack_forget()
            self._work_frame.pack(fill="both", expand=True)
            display = self.app_state.project_name
            if self.app_state.stage_name and self.app_state.stage_name != "Общее":
                display += f" → {self.app_state.stage_name}"
            self._lbl_project.configure(text=display)
            self._update_indicator()
            if self.app_state.status in ("paused", "on_break"):
                self._btn_resume.pack(pady=(6, 0), before=self._btn_stop)
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
            label = "пауза" if self.app_state.status == "paused" else "перерыв"
            m, s = divmod(self._pause_seconds_display, 60)
            self._lbl_pause_info.configure(text=f"{label}: {m:02d}:{s:02d}")

        # Обновляем отображение чистого рабочего времени
        h, rem = divmod(self.app_state.work_seconds, 3600)
        m, s = divmod(rem, 60)
        self._lbl_timer.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

        self._timer_job = self.after(1000, self._tick)

    # --- Действия ---

    def _start_work(self):
        """Начинает рабочую сессию."""
        project_name = self._project_var.get()
        stage_name = self._stage_var.get()

        if not project_name or project_name == "➕ Новый проект...":
            return
        if not stage_name or stage_name == "➕ Новый этап...":
            return

        session_id = start_session(project_name, stage_name)
        self.app_state.session_id = session_id
        self.app_state.project_name = project_name
        self.app_state.stage_name = stage_name
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
            pause_sec = max(non_work, 0)

        end_session(self.app_state.session_id, self.app_state.work_seconds, pause_sec, break_sec)
        self.app_state.reset()
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
        self._btn_resume.pack(pady=(6, 0), before=self._btn_stop)

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
        self._btn_resume.pack(pady=(6, 0), before=self._btn_stop)

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
