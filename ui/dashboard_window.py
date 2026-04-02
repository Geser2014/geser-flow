"""
Окно дашборда — статистика, фильтры, таблица сессий, экспорт.
"""

import csv
import os
import tkinter as tk
import math
from datetime import datetime, timedelta

import customtkinter as ctk
from db import (get_stats_range, get_daily_totals, get_projects,
                get_projects_with_stages_stats, delete_project, delete_stage,
                get_project_id_by_name, get_stage_id)

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

    def _refresh(self):
        """Пересчитывает даты из текущего периода и обновляет всё."""
        self._apply_period(self._period_var.get())

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
