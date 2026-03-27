"""
Окно дашборда — статистика, фильтры, таблица сессий, экспорт.
"""

import csv
import os
from datetime import datetime, timedelta

import customtkinter as ctk
from db import get_stats_range, get_daily_totals, get_projects, get_projects_with_stages_stats

_ICON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")

BG_MAIN = "#1a1a1a"
BG_CARD = "#242424"
BG_ROW_ALT = "#2a2a2a"
TEXT = "#e0e0e0"
ACCENT = "#3d8ef0"
MUTED = "#888888"
HEADER_BG = "#1e1e1e"


def _fmt_hm(seconds: int) -> str:
    """Форматирует секунды в «Xч Yм»."""
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h > 0:
        return f"{h}ч {m}м"
    return f"{m}м"


class DashboardWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Geser Flow — Дашборд")
        self.geometry("800x560")
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

        # Таблица
        self._table_frame = ctk.CTkScrollableFrame(
            self, fg_color=BG_MAIN, corner_radius=0,
        )
        self._table_frame.pack(fill="both", expand=True, padx=15, pady=6)

        # Заголовок таблицы
        self._columns = ["Проект", "Работа", "Паузы", "Перекуры", "Сессий"]
        col_widths = [160, 75, 65, 65, 50]

        header_row = ctk.CTkFrame(self._table_frame, fg_color=HEADER_BG, height=30)
        header_row.pack(fill="x", pady=(0, 2))
        header_row.pack_propagate(False)

        # Spacer for expand button
        ctk.CTkLabel(header_row, text="", width=30).pack(side="left", padx=1)

        for i, col_name in enumerate(self._columns):
            ctk.CTkLabel(
                header_row, text=col_name, width=col_widths[i], height=28,
                fg_color="transparent",
                text_color=MUTED, font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(side="left", padx=1)

        self._rows_container = ctk.CTkFrame(self._table_frame, fg_color="transparent")
        self._rows_container.pack(fill="both", expand=True)

        # Нижняя строка итогов
        self._lbl_totals = ctk.CTkLabel(
            self, text="", font=("Segoe UI", 12), text_color=MUTED,
        )
        self._lbl_totals.pack(fill="x", padx=15, pady=(0, 10))

    def _update_summary_cards(self):
        """Обновляет 4 карточки суммарной статистики."""
        today = datetime.now().strftime("%Y-%m-%d")
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        month_start = datetime.now().strftime("%Y-%m-01")
        year_start = datetime.now().strftime("%Y-01-01")

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
            d_from = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
            d_to = today.strftime("%Y-%m-%d")
        elif period == "month":
            d_from = today.strftime("%Y-%m-01")
            d_to = today.strftime("%Y-%m-%d")
        elif period == "year":
            d_from = today.strftime("%Y-01-01")
            d_to = today.strftime("%Y-%m-%d")
        else:
            d_from = d_to = today.strftime("%Y-%m-%d")

        self._date_from_var.set(d_from)
        self._date_to_var.set(d_to)
        self._refresh()

    def _refresh(self):
        project_list = ["Все проекты"] + get_projects()
        self._project_menu.configure(values=project_list)
        self._update_summary_cards()
        self._render_table()

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

            # Bind double-click for expand/collapse
            row_frame.bind("<Double-Button-1>", lambda e, pn=project_name: self._toggle_expand(pn))

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

        self._lbl_totals.configure(
            text=f"Проектов: {len(projects_data)}  |  Рабочих часов: {_fmt_hm(total_work)}  |  Сессий: {total_sessions}"
        )

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
