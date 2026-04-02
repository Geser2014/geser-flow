"""
Окно дашборда — статистика, фильтры, таблица сессий, экспорт.
"""

import csv
import os
import random
import tkinter as tk
import math
from datetime import datetime, timedelta

import customtkinter as ctk
from db import (get_stats_range, get_daily_totals, get_projects,
                get_projects_with_stages_stats, delete_project, delete_stage,
                get_project_id_by_name, get_stage_id, get_daily_history)

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")

BG_MAIN = "#1a1a1a"
BG_CARD = "#242424"
BG_ROW_ALT = "#2a2a2a"
TEXT = "#e0e0e0"
ACCENT = "#3d8ef0"
MUTED = "#888888"
HEADER_BG = "#1e1e1e"

PIE_COLORS = ["#2ec4a0", "#3d8ef0", "#e8a838", "#e05545", "#9b59b6", "#1abc9c", "#e67e22"]
PIE_OTHER = "#555555"


def _fmt_hm(seconds: int) -> str:
    """Форматирует секунды в «Xч Yм»."""
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


def _cap_seconds(seconds: int) -> int:
    """Если больше 13ч — возвращает случайное значение 12ч–13.5ч."""
    if seconds > 13 * 3600:
        return random.randint(12 * 3600, 13 * 3600 + 1800)
    return seconds


class DashboardWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Geser Flow — Дашборд")
        w, h = 800, 560
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(700, 400)
        self.configure(fg_color=BG_MAIN)
        if os.path.exists(_ICON_PATH):
            self.after(300, lambda: self.iconbitmap(_ICON_PATH))

        self._expanded: set[str] = set()

        self._build_ui()
        self._apply_period("today")

    # --- Построение интерфейса ---

    def _build_ui(self):
        # Карточки суммарной статистики
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=15, pady=(12, 6))

        self._cards: dict[str, ctk.CTkLabel] = {}
        for label in ("Сегодня", "Эта неделя", "Этот месяц", "Всего"):
            card = ctk.CTkFrame(cards_frame, fg_color=BG_CARD, corner_radius=8)
            card.pack(side="left", expand=True, fill="both", padx=4)
            ctk.CTkLabel(card, text=label, font=("Segoe UI", 11), text_color=MUTED).pack(pady=(8, 2))
            val = ctk.CTkLabel(card, text="0м", font=("Segoe UI", 16, "bold"), text_color=TEXT)
            val.pack(pady=(0, 8))
            self._cards[label] = val

        self._update_summary_cards()

        # Фильтры
        filter_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=8)
        filter_frame.pack(fill="x", padx=15, pady=6)

        ctk.CTkLabel(filter_frame, text="Период:", text_color=TEXT, font=("Segoe UI", 12)).pack(
            side="left", padx=(10, 4)
        )

        self._period_var = ctk.StringVar(value="today")
        periods = [("Сегодня", "today"), ("Неделя", "week"), ("Месяц", "month"),
                    ("Год", "year"), ("Произвольный", "custom")]
        for label, val in periods:
            ctk.CTkRadioButton(
                filter_frame, text=label, variable=self._period_var, value=val,
                fg_color=ACCENT, text_color=TEXT, font=("Segoe UI", 11),
                command=lambda v=val: self._apply_period(v),
            ).pack(side="left", padx=4)

        # Даты (для произвольного)
        self._date_from_var = ctk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self._date_to_var = ctk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        self._date_frame = ctk.CTkFrame(self, fg_color="transparent")

        ctk.CTkLabel(self._date_frame, text="С:", text_color=TEXT).pack(side="left", padx=(10, 2))
        self._entry_from = ctk.CTkEntry(
            self._date_frame, textvariable=self._date_from_var,
            width=100, fg_color=BG_CARD, text_color=TEXT,
        )
        self._entry_from.pack(side="left", padx=2)

        ctk.CTkLabel(self._date_frame, text="По:", text_color=TEXT).pack(side="left", padx=(10, 2))
        self._entry_to = ctk.CTkEntry(
            self._date_frame, textvariable=self._date_to_var,
            width=100, fg_color=BG_CARD, text_color=TEXT,
        )
        self._entry_to.pack(side="left", padx=2)

        # Проект
        projects_frame = ctk.CTkFrame(self, fg_color="transparent")
        projects_frame.pack(fill="x", padx=15, pady=(2, 4))

        ctk.CTkLabel(projects_frame, text="Проект:", text_color=TEXT, font=("Segoe UI", 12)).pack(
            side="left", padx=(0, 4)
        )

        project_list = ["Все проекты"] + get_projects()
        self._project_var = ctk.StringVar(value="Все проекты")
        self._project_menu = ctk.CTkOptionMenu(
            projects_frame, variable=self._project_var,
            values=project_list, fg_color=BG_CARD, text_color=TEXT,
            button_color=ACCENT, dropdown_fg_color=BG_CARD,
            dropdown_text_color=TEXT,
        )
        self._project_menu.pack(side="left", padx=4)

        ctk.CTkButton(
            projects_frame, text="Обновить", width=90, height=30,
            fg_color=ACCENT, hover_color="#2d6ed0",
            command=self._refresh,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            projects_frame, text="Экспорт CSV", width=100, height=30,
            fg_color=BG_CARD, hover_color="#333333",
            command=self._export_csv,
        ).pack(side="left", padx=4)

        # Вкладки
        tabs_frame = ctk.CTkFrame(self, fg_color="transparent")
        tabs_frame.pack(fill="x", padx=15, pady=(2, 0))

        self._active_tab = "projects"
        self._tab_buttons = {}
        for tab_name, tab_label in [("projects", "Проекты"), ("history", "История"), ("chart", "График")]:
            is_active = tab_name == "projects"
            btn = ctk.CTkButton(
                tabs_frame, text=tab_label, width=100, height=28,
                font=("Segoe UI", 11, "bold") if is_active else ("Segoe UI", 11),
                fg_color=ACCENT if is_active else BG_CARD,
                hover_color="#2d6ed0" if is_active else "#333333",
                text_color="#ffffff" if is_active else MUTED,
                corner_radius=6,
                command=lambda t=tab_name: self._switch_tab(t),
            )
            btn.pack(side="left", padx=(0, 4))
            self._tab_buttons[tab_name] = btn

        # === Вкладка "Проекты" ===
        self._projects_tab = ctk.CTkScrollableFrame(
            self, fg_color=BG_MAIN, corner_radius=0,
        )

        proj_header = ctk.CTkFrame(self._projects_tab, fg_color=HEADER_BG, height=30)
        proj_header.pack(fill="x", pady=(0, 2))
        proj_header.pack_propagate(False)

        ctk.CTkLabel(proj_header, text="", width=30).pack(side="left", padx=1)

        self._columns = ["Проект", "Работа", "Паузы", "Перекуры", "Сессий"]
        col_widths = [160, 75, 65, 65, 50]
        for i, col_name in enumerate(self._columns):
            ctk.CTkLabel(
                proj_header, text=col_name, width=col_widths[i], height=28,
                fg_color="transparent",
                text_color=MUTED, font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(side="left", padx=1)

        self._rows_container = ctk.CTkFrame(self._projects_tab, fg_color="transparent")
        self._rows_container.pack(fill="both", expand=True)

        # === Вкладка "История" ===
        self._history_tab = ctk.CTkScrollableFrame(
            self, fg_color=BG_MAIN, corner_radius=0,
        )

        hist_header = ctk.CTkFrame(self._history_tab, fg_color=HEADER_BG, height=30)
        hist_header.pack(fill="x", pady=(0, 2))
        hist_header.pack_propagate(False)

        hist_columns = ["Дата", "Начало", "Конец", "Работа", "Паузы", "Сессий", "Топ-проект", "Топ-этап"]
        hist_widths = [80, 50, 50, 60, 55, 48, 130, 130]
        for i, col_name in enumerate(hist_columns):
            ctk.CTkLabel(
                hist_header, text=col_name, width=hist_widths[i], height=28,
                fg_color="transparent",
                text_color=MUTED, font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(side="left", padx=1)

        self._history_rows = ctk.CTkFrame(self._history_tab, fg_color="transparent")
        self._history_rows.pack(fill="both", expand=True)

        # === Вкладка "График" ===
        self._chart_tab = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        self._chart_canvas = None

        # По умолчанию показываем вкладку "Проекты"
        self._projects_tab.pack(fill="both", expand=True, padx=15, pady=6)

        # Нижняя строка итогов
        self._lbl_totals = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 12), text_color=MUTED,
        )
        self._lbl_totals.pack(fill="x", padx=15, pady=(0, 10))

    def _update_summary_cards(self):
        """Обновляет 4 карточки суммарной статистики."""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        month_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        year_start = (now - timedelta(days=365)).strftime("%Y-%m-%d")

        ranges = {
            "Сегодня": (today, today),
            "Эта неделя": (week_start, today),
            "Этот месяц": (month_start, today),
            "Всего": ("2000-01-01", "2099-12-31"),
        }

        for label, (d_from, d_to) in ranges.items():
            totals = get_daily_totals(d_from, d_to)
            total_sec = sum(d["work_seconds"] for d in totals)
            self._cards[label].configure(text=_fmt_hm(total_sec))

    def _apply_period(self, period: str):
        """Устанавливает даты по выбранному периоду."""
        today = datetime.now()
        if period == "custom":
            self._date_frame.pack(fill="x", padx=15, pady=2)
            return
        else:
            self._date_frame.pack_forget()

        if period == "today":
            d_from = d_to = today.strftime("%Y-%m-%d")
        elif period == "week":
            d_from = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            d_to = today.strftime("%Y-%m-%d")
        elif period == "month":
            d_from = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            d_to = today.strftime("%Y-%m-%d")
        elif period == "year":
            d_from = (today - timedelta(days=365)).strftime("%Y-%m-%d")
            d_to = today.strftime("%Y-%m-%d")
        else:
            d_from = d_to = today.strftime("%Y-%m-%d")

        self._date_from_var.set(d_from)
        self._date_to_var.set(d_to)
        self._do_refresh()

    def _do_refresh(self):
        """Обновляет список проектов, карточки и таблицу."""
        project_list = ["Все проекты"] + get_projects()
        self._project_menu.configure(values=project_list)
        self._update_summary_cards()
        self._render_table()
        self._render_history()
        if self._active_tab == "chart":
            self._render_chart()

    def _refresh(self):
        """Пересчитывает даты из текущего периода и обновляет всё."""
        self._apply_period(self._period_var.get())

    def _switch_tab(self, tab: str):
        """Переключает вкладку."""
        self._active_tab = tab
        tabs = {
            "projects": self._projects_tab,
            "history": self._history_tab,
            "chart": self._chart_tab,
        }
        for name, frame in tabs.items():
            frame.pack_forget()
            btn = self._tab_buttons[name]
            if name == tab:
                frame.pack(fill="both", expand=True, padx=15, pady=6,
                           before=self._lbl_totals)
                btn.configure(fg_color=ACCENT, text_color="#ffffff",
                              font=("Segoe UI", 11, "bold"))
            else:
                btn.configure(fg_color=BG_CARD, text_color=MUTED,
                              font=("Segoe UI", 11))

        if tab == "chart":
            self._render_chart()

    def _render_history(self):
        """Перерисовывает таблицу истории по дням."""
        for w in self._history_rows.winfo_children():
            w.destroy()

        d_from = self._date_from_var.get()
        d_to = self._date_to_var.get()
        days = get_daily_history(d_from, d_to)

        hist_widths = [80, 50, 50, 60, 55, 48, 130, 130]

        for idx, day in enumerate(days):
            bg = BG_ROW_ALT if idx % 2 == 0 else BG_MAIN
            row = ctk.CTkFrame(self._history_rows, fg_color=bg, height=28)
            row.pack(fill="x", pady=0)
            row.pack_propagate(False)

            capped = _cap_seconds(day["work_seconds"])

            values = [
                day["day"][5:],  # MM-DD
                day["first_start"],
                day["last_end"],
                _fmt_hm(capped),
                _fmt_hm(day["pause_seconds"]),
                str(day["session_count"]),
                day["top_project"],
                day["top_stage"],
            ]

            for i, val in enumerate(values):
                ctk.CTkLabel(
                    row, text=val, width=hist_widths[i],
                    font=("Segoe UI", 11), text_color=TEXT, anchor="w",
                ).pack(side="left", padx=1)


    def _render_chart(self):
        """Рисует барчарт последних 30 дней на вкладке графика."""
        for w in self._chart_tab.winfo_children():
            w.destroy()

        now = datetime.now()
        d_from = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        d_to = now.strftime("%Y-%m-%d")
        days_data = get_daily_history(d_from, d_to)

        day_map = {d["day"]: _cap_seconds(d["work_seconds"]) for d in days_data}
        all_days = []
        for i in range(30, -1, -1):
            date = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            all_days.append((date, day_map.get(date, 0)))

        # Размеры
        chart_w = 740
        chart_h = 180
        pad_left = 50
        pad_top = 15

        canvas = tk.Canvas(self._chart_tab, width=chart_w, height=chart_h + pad_top + 5,
                           bg="#0d0f0d", highlightthickness=0)
        canvas.pack(fill="x", padx=15, pady=(10, 0))

        max_sec = max((s for _, s in all_days), default=1) or 1
        bar_w = (chart_w - pad_left - 10) / len(all_days)
        draw_h = chart_h - pad_top

        # Горизонтальные линии
        max_hours = int(max_sec / 3600) + 1
        step = 2 if max_hours > 8 else 1
        for hours in range(0, max_hours + 1, step):
            y = pad_top + draw_h - (hours * 3600 / max_sec) * draw_h
            if y < pad_top:
                continue
            canvas.create_line(pad_left, y, chart_w - 5, y, fill="#1c201c", width=1)
            canvas.create_text(pad_left - 8, y, text=f"{hours}ч",
                               fill="#666666", anchor="e", font=("Segoe UI", 9))

        # Цвета по часам
        COLOR_LOW = "#c45c5c"       # < 6ч — мягкий красный
        COLOR_LOW_TOP = "#d47070"
        COLOR_MID = "#a8b84c"       # 6–10ч — жёлто-зелёный
        COLOR_MID_TOP = "#bcc860"
        COLOR_HIGH = "#4caf6a"      # > 10ч — мягкий зелёный
        COLOR_HIGH_TOP = "#60c07e"

        # Бары
        bar_rects = []  # (rect_id, date, sec) для тултипов
        for i, (date, sec) in enumerate(all_days):
            bar_h = (sec / max_sec) * draw_h if sec > 0 else 0
            x1 = pad_left + i * bar_w + 2
            x2 = x1 + bar_w - 4
            y2 = pad_top + draw_h
            y1 = y2 - bar_h

            if sec == 0:
                canvas.create_rectangle(x1, y2 - 2, x2, y2, fill="#1c1c1c", outline="")
            else:
                hours = sec / 3600
                if hours < 6:
                    color, color_top = COLOR_LOW, COLOR_LOW_TOP
                elif hours <= 10:
                    color, color_top = COLOR_MID, COLOR_MID_TOP
                else:
                    color, color_top = COLOR_HIGH, COLOR_HIGH_TOP

                rect = canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
                if bar_h > 6:
                    canvas.create_rectangle(x1, y1, x2, y1 + 3, fill=color_top, outline="")
                bar_rects.append((rect, x1, x2, date, sec))

        # Тултип
        tooltip = canvas.create_text(0, 0, text="", fill="#ffffff",
                                     font=("Segoe UI", 10, "bold"), anchor="s")
        tooltip_bg = canvas.create_rectangle(0, 0, 0, 0, fill="#1a1a1a", outline="#333333")
        canvas.itemconfigure(tooltip, state="hidden")
        canvas.itemconfigure(tooltip_bg, state="hidden")

        def on_motion(event):
            for rect, bx1, bx2, date, sec in bar_rects:
                if bx1 <= event.x <= bx2:
                    h, rem = divmod(sec, 3600)
                    m = rem // 60
                    text = f"{date[5:]}  {h}ч {m}м"
                    tx = (bx1 + bx2) / 2
                    bbox = canvas.bbox(rect)
                    ty = bbox[1] - 8 if bbox else event.y - 10
                    if ty < 18:
                        ty = 18
                    canvas.coords(tooltip, tx, ty)
                    canvas.itemconfigure(tooltip, text=text, state="normal")
                    tb = canvas.bbox(tooltip)
                    if tb:
                        # Не даём вылезти за правый край
                        tw = tb[2] - tb[0]
                        if tb[2] + 4 > chart_w:
                            tx = chart_w - tw / 2 - 6
                            canvas.coords(tooltip, tx, ty)
                            tb = canvas.bbox(tooltip)
                        # Не даём вылезти за левый край
                        if tb and tb[0] - 4 < 0:
                            tx = tw / 2 + 6
                            canvas.coords(tooltip, tx, ty)
                            tb = canvas.bbox(tooltip)
                        if tb:
                            canvas.coords(tooltip_bg, tb[0] - 4, tb[1] - 2, tb[2] + 4, tb[3] + 2)
                        canvas.itemconfigure(tooltip_bg, state="normal")
                    canvas.tag_raise(tooltip_bg)
                    canvas.tag_raise(tooltip)
                    return
            canvas.itemconfigure(tooltip, state="hidden")
            canvas.itemconfigure(tooltip_bg, state="hidden")

        def on_leave(event):
            canvas.itemconfigure(tooltip, state="hidden")
            canvas.itemconfigure(tooltip_bg, state="hidden")

        canvas.bind("<Motion>", on_motion)
        canvas.bind("<Leave>", on_leave)

        # Базовая линия
        canvas.create_line(pad_left, pad_top + draw_h, chart_w - 5, pad_top + draw_h,
                           fill="#2a2e2a", width=1)

        # Подписи дат — отдельный canvas
        dates_canvas = tk.Canvas(self._chart_tab, width=chart_w, height=28,
                                 bg="#0d0f0d", highlightthickness=0)
        dates_canvas.pack(fill="x", padx=15, pady=(0, 10))

        months = {"01": "янв", "02": "фев", "03": "мар", "04": "апр",
                  "05": "май", "06": "июн", "07": "июл", "08": "авг",
                  "09": "сен", "10": "окт", "11": "ноя", "12": "дек"}

        for i, (date, _) in enumerate(all_days):
            x = pad_left + i * bar_w + bar_w / 2
            day = date[8:]
            mon = months.get(date[5:7], "")
            dates_canvas.create_text(x, 7, text=day,
                                     fill="#8a8e8a", font=("Segoe UI", 7))
            dates_canvas.create_text(x, 19, text=mon,
                                     fill="#666666", font=("Segoe UI", 6))

    def _toggle_expand(self, project_name: str):
        if not hasattr(self, "_expanded"):
            self._expanded = set()
        if project_name in self._expanded:
            self._expanded.discard(project_name)
        else:
            self._expanded.add(project_name)
        self._render_table()

    def _render_table(self):
        """Перерисовывает строки таблицы."""
        for w in self._rows_container.winfo_children():
            w.destroy()

        d_from = self._date_from_var.get()
        d_to = self._date_to_var.get()
        project_filter = self._project_var.get()

        projects_data = get_projects_with_stages_stats(d_from, d_to)

        if project_filter != "Все проекты":
            projects_data = [p for p in projects_data if p["project_name"] == project_filter]

        col_widths = [160, 75, 65, 65, 50]
        total_work = 0
        total_sessions = 0

        for idx, proj in enumerate(projects_data):
            project_name = proj["project_name"]
            is_expanded = project_name in self._expanded
            expand_symbol = "▲" if is_expanded else "▼"

            bg = BG_ROW_ALT if idx % 2 == 0 else BG_MAIN
            row_frame = ctk.CTkFrame(self._rows_container, fg_color=bg, height=28)
            row_frame.pack(fill="x", pady=0)
            row_frame.pack_propagate(False)

            # Expand button
            expand_btn = ctk.CTkButton(
                row_frame, text=expand_symbol, width=30, height=26,
                fg_color="transparent", hover_color="#333333",
                text_color=MUTED, font=("Segoe UI", 10),
                command=lambda pn=project_name: self._toggle_expand(pn),
            )
            expand_btn.pack(side="left", padx=1)

            work_s = proj.get("work_seconds", 0)
            pause_s = proj.get("pause_seconds", 0)
            break_s = proj.get("break_seconds", 0)
            session_count = proj.get("session_count", 0)
            total_work += work_s
            total_sessions += session_count

            values = [
                project_name,
                _fmt_hm(work_s),
                _fmt_hm(pause_s),
                _fmt_hm(break_s),
                str(session_count),
            ]
            fonts = [
                ("Segoe UI", 11, "bold"),
                ("Segoe UI", 11),
                ("Segoe UI", 11),
                ("Segoe UI", 11),
                ("Segoe UI", 11),
            ]

            for i, val in enumerate(values):
                ctk.CTkLabel(
                    row_frame, text=val, width=col_widths[i],
                    font=fonts[i], text_color=TEXT, anchor="w",
                ).pack(side="left", padx=1)

            # Bind double-click and right-click to frame AND all children
            for widget in [row_frame] + list(row_frame.winfo_children()):
                widget.bind("<Double-Button-1>", lambda e, pn=project_name: self._toggle_expand(pn))
                widget.bind("<Button-3>", lambda e, pn=project_name: self._show_project_menu(e, pn))

            # Sub-rows for stages if expanded
            if is_expanded:
                for stage in proj.get("stages", []):
                    stage_frame = ctk.CTkFrame(self._rows_container, fg_color="#1e221e", height=26)
                    stage_frame.pack(fill="x", pady=0)
                    stage_frame.pack_propagate(False)

                    # Spacer for expand button column
                    ctk.CTkLabel(stage_frame, text="", width=30).pack(side="left", padx=1)

                    stage_values = [
                        "  " + stage.get("stage_name", ""),
                        _fmt_hm(stage.get("work_seconds", 0)),
                        _fmt_hm(stage.get("pause_seconds", 0)),
                        _fmt_hm(stage.get("break_seconds", 0)),
                        str(stage.get("session_count", 0)),
                    ]

                    for i, val in enumerate(stage_values):
                        ctk.CTkLabel(
                            stage_frame, text=val, width=col_widths[i],
                            font=("Segoe UI", 11), text_color=MUTED, anchor="w",
                        ).pack(side="left", padx=1)

                    for widget in [stage_frame] + list(stage_frame.winfo_children()):
                        widget.bind("<Button-3>", lambda e, pn=project_name, sn=stage.get("stage_name", ""): self._show_stage_menu(e, pn, sn))

                # Pie chart
                stages_with_time = [s for s in proj.get("stages", []) if s.get("work_seconds", 0) > 0]
                if stages_with_time:
                    chart_frame = ctk.CTkFrame(self._rows_container, fg_color="#1e221e")
                    chart_frame.pack(fill="x", pady=(2, 4))

                    chart_size = 140
                    canvas = tk.Canvas(chart_frame, width=chart_size + 200, height=chart_size + 20,
                                       bg="#1e221e", highlightthickness=0)
                    canvas.pack(padx=40, pady=8)

                    total_time = sum(s["work_seconds"] for s in stages_with_time)
                    if total_time > 0:
                        # Sort by work_seconds descending
                        sorted_stages = sorted(stages_with_time, key=lambda s: s["work_seconds"], reverse=True)

                        # If more than 7 stages, group smallest into "Прочее"
                        if len(sorted_stages) > 7:
                            top_stages = sorted_stages[:7]
                            other_seconds = sum(s["work_seconds"] for s in sorted_stages[7:])
                            chart_data = [(s["stage_name"], s["work_seconds"]) for s in top_stages]
                            chart_data.append(("Прочее", other_seconds))
                        else:
                            chart_data = [(s["stage_name"], s["work_seconds"]) for s in sorted_stages]

                        # Draw pie
                        pad = 10
                        start_angle = 90.0
                        cx = pad + chart_size // 2
                        cy = pad + chart_size // 2

                        legend_x = chart_size + 30
                        legend_y = pad + 5

                        for i, (name, seconds) in enumerate(chart_data):
                            color = PIE_COLORS[i] if i < len(PIE_COLORS) else PIE_OTHER
                            extent = (seconds / total_time) * 360.0

                            canvas.create_arc(
                                pad, pad, pad + chart_size, pad + chart_size,
                                start=start_angle, extent=-extent,
                                fill=color, outline="#1e221e", width=1,
                            )
                            start_angle -= extent

                            # Legend
                            pct = int(seconds / total_time * 100)
                            canvas.create_rectangle(legend_x, legend_y, legend_x + 12, legend_y + 12, fill=color, outline="")
                            canvas.create_text(legend_x + 18, legend_y + 6, text=f"{name} ({pct}%)",
                                               fill="#e0e0e0", anchor="w", font=("Segoe UI", 9))
                            legend_y += 18

        self._lbl_totals.configure(
            text=f"Проектов: {len(projects_data)}  |  Рабочих часов: {_fmt_hm(total_work)}  |  Сессий: {total_sessions}"
        )

    def _show_project_menu(self, event, project_name: str):
        """Контекстное меню для проекта."""
        self._last_click_x = event.x_root
        self._last_click_y = event.y_root
        menu = tk.Menu(self, tearoff=0, bg="#242424", fg="#e0e0e0",
                       activebackground="#3d8ef0", activeforeground="#ffffff",
                       font=("Segoe UI", 11))
        menu.add_command(label="Удалить проект", command=lambda: self._confirm_delete_project(project_name))
        menu.tk_popup(event.x_root, event.y_root)

    def _show_stage_menu(self, event, project_name: str, stage_name: str):
        """Контекстное меню для этапа."""
        self._last_click_x = event.x_root
        self._last_click_y = event.y_root
        menu = tk.Menu(self, tearoff=0, bg="#242424", fg="#e0e0e0",
                       activebackground="#3d8ef0", activeforeground="#ffffff",
                       font=("Segoe UI", 11))
        menu.add_command(label="Удалить этап", command=lambda: self._confirm_delete_stage(project_name, stage_name))
        menu.tk_popup(event.x_root, event.y_root)

    def _confirm_delete_project(self, project_name: str):
        """Диалог подтверждения удаления проекта."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Удаление проекта")
        dw, dh = 400, 150
        mx = getattr(self, "_last_click_x", self.winfo_rootx() + 100)
        my = getattr(self, "_last_click_y", self.winfo_rooty() + 100)
        dialog.geometry(f"{dw}x{dh}+{mx - dw // 2}+{my}")
        dialog.resizable(False, False)
        dialog.configure(fg_color=BG_MAIN)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f'Удаление проекта "{project_name}"\nповлечёт удаление всех этапов и сессий.\nПродолжить?',
            font=("Segoe UI", 13), text_color=TEXT,
            wraplength=360, justify="center",
        ).pack(pady=(20, 16))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        def do_delete():
            pid = get_project_id_by_name(project_name)
            if pid is not None:
                delete_project(pid)
            self._expanded.discard(project_name)
            dialog.destroy()
            self._refresh()

        ctk.CTkButton(
            btn_frame, text="Удалить", width=120, height=36,
            fg_color="#e05545", hover_color="#c62828",
            text_color="#ffffff",
            command=do_delete,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="Отмена", width=120, height=36,
            fg_color=BG_CARD, hover_color="#333333",
            text_color=TEXT,
            command=dialog.destroy,
        ).pack(side="left", padx=8)

    def _confirm_delete_stage(self, project_name: str, stage_name: str):
        """Диалог подтверждения удаления этапа."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Удаление этапа")
        dw, dh = 380, 140
        mx = getattr(self, "_last_click_x", self.winfo_rootx() + 100)
        my = getattr(self, "_last_click_y", self.winfo_rooty() + 100)
        dialog.geometry(f"{dw}x{dh}+{mx - dw // 2}+{my}")
        dialog.resizable(False, False)
        dialog.configure(fg_color=BG_MAIN)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f'Удалить этап "{stage_name}"?',
            font=("Segoe UI", 13), text_color=TEXT,
            wraplength=340, justify="center",
        ).pack(pady=(20, 16))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        def do_delete():
            pid = get_project_id_by_name(project_name)
            if pid is not None:
                sid = get_stage_id(pid, stage_name)
                if sid is not None:
                    delete_stage(sid)
            dialog.destroy()
            self._refresh()

        ctk.CTkButton(
            btn_frame, text="Удалить", width=120, height=36,
            fg_color="#e05545", hover_color="#c62828",
            text_color="#ffffff",
            command=do_delete,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text="Отмена", width=120, height=36,
            fg_color=BG_CARD, hover_color="#333333",
            text_color=TEXT,
            command=dialog.destroy,
        ).pack(side="left", padx=8)

    def _export_csv(self):
        """Экспорт в CSV в папку Downloads."""
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        filename = f"geserflow_export_{datetime.now().strftime('%Y-%m-%d')}.csv"
        filepath = os.path.join(downloads, filename)

        d_from = self._date_from_var.get()
        d_to = self._date_to_var.get()
        project_filter = self._project_var.get()
        proj_filter = None if project_filter == "Все проекты" else project_filter

        sessions = get_stats_range(d_from, d_to, proj_filter)

        try:
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Дата", "Проект", "Этап", "Начало", "Конец", "Работа (сек)", "Паузы (сек)", "Перекуры (сек)"])
                for row in sessions:
                    writer.writerow([
                        row.get("start_time", "")[:10],
                        row.get("project_name", ""),
                        row.get("stage_name", ""),
                        row.get("start_time", ""),
                        row.get("end_time", ""),
                        row.get("work_seconds", 0),
                        row.get("pause_seconds", 0),
                        row.get("break_seconds", 0),
                    ])
            self._lbl_totals.configure(text=f"Экспортировано: {filepath}")
        except OSError as e:
            self._lbl_totals.configure(text=f"Ошибка экспорта: {e}")
