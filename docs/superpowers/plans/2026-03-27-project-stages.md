# Project Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hierarchical project→stage structure with dropdowns on the main screen and expandable stage rows in the dashboard.

**Architecture:** New `stages` table in SQLite with FK to `projects`. Sessions get a `stage_id` FK. Migration creates "Общее" stage for existing projects. Main window replaces text input with two dropdowns. Dashboard rows become project-level with expandable stage sub-rows.

**Tech Stack:** Python 3.12, customtkinter, SQLite3, PIL

---

### Task 1: Database — stages table + migration

**Files:**
- Modify: `db.py`

- [ ] **Step 1: Add stages table to init_db()**

In `db.py`, add the `stages` table creation to `init_db()` and the `stage_id` column to sessions. Add it after existing `CREATE TABLE` statements inside the `executescript`:

```python
def init_db() -> None:
    """Создаёт таблицы если не существуют."""
    conn = _connect()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                name TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(project_id, name)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id),
                stage_id INTEGER REFERENCES stages(id),
                start_time TEXT NOT NULL,
                end_time TEXT,
                work_seconds INTEGER DEFAULT 0,
                pause_seconds INTEGER DEFAULT 0,
                break_seconds INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS pauses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES sessions(id),
                start_time TEXT NOT NULL,
                end_time TEXT,
                type TEXT NOT NULL
            );
        """)
        conn.commit()

        # Migration: add stage_id column if missing (existing DB)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "stage_id" not in cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN stage_id INTEGER REFERENCES stages(id)")
            conn.commit()

        # Migration: create "Общее" stage for projects that don't have any stages
        projects_without_stages = conn.execute("""
            SELECT id FROM projects
            WHERE id NOT IN (SELECT DISTINCT project_id FROM stages)
        """).fetchall()
        for row in projects_without_stages:
            conn.execute(
                "INSERT INTO stages (project_id, name) VALUES (?, ?)",
                (row[0], "Общее"),
            )
        conn.commit()

        # Migration: assign stage_id to sessions that don't have one
        conn.execute("""
            UPDATE sessions
            SET stage_id = (
                SELECT st.id FROM stages st
                WHERE st.project_id = sessions.project_id AND st.name = 'Общее'
            )
            WHERE stage_id IS NULL
        """)
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Run app to verify migration works**

Run: `cd C:/Users/User/GeserFlow && python -c "from db import init_db; init_db(); print('OK')"`
Expected: `OK` — no errors, stages table created, existing sessions migrated.

- [ ] **Step 3: Commit**

```bash
git add db.py
git commit -m "feat(db): add stages table and migration"
```

---

### Task 2: Database — stage CRUD and query functions

**Files:**
- Modify: `db.py`

- [ ] **Step 1: Add get_or_create_stage()**

Add after `get_or_create_project()` in `db.py`:

```python
def get_or_create_stage(project_id: int, stage_name: str) -> int:
    """Возвращает id этапа, создаёт если не существует."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id FROM stages WHERE project_id = ? AND name = ?",
            (project_id, stage_name),
        ).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO stages (project_id, name) VALUES (?, ?)",
            (project_id, stage_name),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
```

- [ ] **Step 2: Add get_stages(project_id)**

Add after `get_or_create_stage()`:

```python
def get_stages(project_id: int) -> list[str]:
    """Этапы проекта, отсортированные по последней активности (свежие первые)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT st.name,
                      MAX(s.start_time) as last_active
               FROM stages st
               LEFT JOIN sessions s ON s.stage_id = st.id AND s.status != 'active'
               WHERE st.project_id = ?
               GROUP BY st.id
               ORDER BY last_active DESC NULLS LAST""",
            (project_id,),
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 3: Add get_projects_sorted()**

Add a new function that returns projects sorted by last session (most recent first):

```python
def get_projects_sorted() -> list[str]:
    """Проекты, отсортированные по последней активности (свежие первые)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT p.name,
                      MAX(s.start_time) as last_active
               FROM projects p
               LEFT JOIN sessions s ON s.project_id = p.id AND s.status != 'active'
               GROUP BY p.id
               ORDER BY last_active DESC NULLS LAST"""
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 4: Add get_last_session_info()**

Returns the project name and stage name of the most recent completed session:

```python
def get_last_session_info() -> tuple[str, str] | None:
    """Возвращает (project_name, stage_name) последней завершённой сессии."""
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT p.name as project_name, st.name as stage_name
               FROM sessions s
               JOIN projects p ON p.id = s.project_id
               JOIN stages st ON st.id = s.stage_id
               WHERE s.status != 'active'
               ORDER BY s.start_time DESC LIMIT 1"""
        ).fetchone()
        if row:
            return (row["project_name"], row["stage_name"])
        return None
    finally:
        conn.close()
```

- [ ] **Step 5: Update start_session() to accept stage**

Modify `start_session()` to take a `stage_name` parameter:

```python
def start_session(project_name: str, stage_name: str = "Общее") -> int:
    """Начинает новую сессию, возвращает session_id."""
    project_id = get_or_create_project(project_name)
    stage_id = get_or_create_stage(project_id, stage_name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO sessions (project_id, stage_id, start_time, status) VALUES (?, ?, ?, 'active')",
            (project_id, stage_id, now),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
```

- [ ] **Step 6: Update get_stats_range() to include stage_name**

Modify the query to JOIN stages and include `stage_name` in results:

```python
def get_stats_range(date_from: str, date_to: str, project_name: str | None = None) -> list[dict]:
    """Список сессий за период с фильтром по проекту."""
    conn = _connect()
    try:
        query = """
            SELECT s.id, p.name as project_name, st.name as stage_name,
                   s.start_time, s.end_time,
                   s.work_seconds, s.pause_seconds, s.break_seconds, s.status
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            LEFT JOIN stages st ON st.id = s.stage_id
            WHERE date(s.start_time) >= ? AND date(s.start_time) <= ?
              AND s.status != 'active'
        """
        params: list = [date_from, date_to]
        if project_name:
            query += " AND p.name = ?"
            params.append(project_name)
        query += " ORDER BY s.start_time DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
```

- [ ] **Step 7: Add get_projects_with_stages_stats()**

New function for the dashboard — returns projects with aggregated stats, and stages within each project:

```python
def get_projects_with_stages_stats(date_from: str, date_to: str) -> list[dict]:
    """Проекты со статистикой + этапы внутри каждого проекта.

    Returns list of dicts:
    {
        'project_name': str,
        'work_seconds': int,
        'pause_seconds': int,
        'break_seconds': int,
        'session_count': int,
        'stages': [
            {'stage_name': str, 'work_seconds': int, 'pause_seconds': int,
             'break_seconds': int, 'session_count': int},
            ...
        ]
    }
    """
    conn = _connect()
    try:
        # Project-level aggregation
        projects = conn.execute(
            """SELECT p.name as project_name,
                      COALESCE(SUM(s.work_seconds), 0) as work_seconds,
                      COALESCE(SUM(s.pause_seconds), 0) as pause_seconds,
                      COALESCE(SUM(s.break_seconds), 0) as break_seconds,
                      COUNT(s.id) as session_count
               FROM projects p
               LEFT JOIN sessions s ON s.project_id = p.id
                    AND s.status != 'active'
                    AND date(s.start_time) >= ? AND date(s.start_time) <= ?
               GROUP BY p.id
               HAVING session_count > 0
               ORDER BY MAX(s.start_time) DESC""",
            (date_from, date_to),
        ).fetchall()

        result = []
        for proj in projects:
            p = dict(proj)
            # Stage-level aggregation for this project
            stages = conn.execute(
                """SELECT st.name as stage_name,
                          COALESCE(SUM(s.work_seconds), 0) as work_seconds,
                          COALESCE(SUM(s.pause_seconds), 0) as pause_seconds,
                          COALESCE(SUM(s.break_seconds), 0) as break_seconds,
                          COUNT(s.id) as session_count
                   FROM stages st
                   LEFT JOIN sessions s ON s.stage_id = st.id
                        AND s.status != 'active'
                        AND date(s.start_time) >= ? AND date(s.start_time) <= ?
                   JOIN projects pr ON pr.id = st.project_id
                   WHERE pr.name = ?
                   GROUP BY st.id
                   ORDER BY st.created_at ASC""",
                (date_from, date_to, p["project_name"]),
            ).fetchall()
            p["stages"] = [dict(s) for s in stages]
            result.append(p)

        return result
    finally:
        conn.close()
```

- [ ] **Step 8: Update get_interrupted_session() to include stage**

```python
def get_interrupted_session() -> dict | None:
    """Находит незавершённую (active) сессию."""
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT s.id, s.start_time, s.work_seconds,
                      p.name as project_name, st.name as stage_name
               FROM sessions s
               JOIN projects p ON p.id = s.project_id
               LEFT JOIN stages st ON st.id = s.stage_id
               WHERE s.status = 'active'
               ORDER BY s.id DESC LIMIT 1"""
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()
```

- [ ] **Step 9: Verify all functions work**

Run: `cd C:/Users/User/GeserFlow && python -c "from db import *; init_db(); print(get_projects_sorted()); print(get_last_session_info())"`
Expected: Lists and None (or data if sessions exist), no errors.

- [ ] **Step 10: Commit**

```bash
git add db.py
git commit -m "feat(db): add stage CRUD, sorted queries, and stats functions"
```

---

### Task 3: State — add stage_name

**Files:**
- Modify: `state.py`

- [ ] **Step 1: Add stage_name to AppState**

In `state.py`, add `stage_name` to `_init_state()`:

```python
def _init_state(self):
    self.session_id: int | None = None
    self.project_name: str = ""
    self.stage_name: str = ""
    self.status: str = "idle"  # idle | working | paused | on_break
    self.session_start: datetime | None = None
    self.work_seconds: int = 0
    self.pause_start: datetime | None = None
    self.pause_id: int | None = None
    self.last_check_time: datetime | None = None
    # Счётчик непрерывной работы для перекуров (в секундах)
    self.continuous_work_seconds: int = 0
```

- [ ] **Step 2: Commit**

```bash
git add state.py
git commit -m "feat(state): add stage_name to AppState"
```

---

### Task 4: MainWindow — replace text input with dropdowns

**Files:**
- Modify: `ui/main_window.py`

- [ ] **Step 1: Update imports**

Replace the imports at the top of `ui/main_window.py`:

```python
import os
import customtkinter as ctk
from state import AppState
from db import (
    get_projects_sorted, get_stages, get_or_create_project,
    get_last_session_info, start_session, end_session,
    start_pause, end_pause, get_stats_today,
)
import config
```

- [ ] **Step 2: Replace idle UI — remove text input and autocomplete, add dropdowns**

Replace the entire idle section in `_build_ui()`. Remove the old text entry, listbox_frame, suggestion_buttons, and autocomplete bindings. Replace with two dropdown sections:

```python
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
        self._lbl_subtitle.pack(pady=(0, 20))

        # Карточка выбора проекта и этапа
        input_card = ctk.CTkFrame(
            self._idle_frame, fg_color=BG_CARD,
            border_width=1, border_color=BORDER, corner_radius=8,
        )
        input_card.pack(fill="x", pady=(0, 5))

        # --- Проект ---
        ctk.CTkLabel(
            input_card, text="ПРОЕКТ",
            font=("Segoe UI", 9), text_color=MUTED,
        ).pack(padx=14, pady=(10, 2), anchor="w")

        self._project_var = ctk.StringVar()
        self._project_menu = ctk.CTkOptionMenu(
            input_card, variable=self._project_var,
            values=[], width=250, height=36,
            fg_color=BG_MAIN, text_color=TEXT,
            button_color=BORDER, button_hover_color=HOVER,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT,
            dropdown_hover_color=HOVER,
            command=self._on_project_selected,
        )
        self._project_menu.pack(padx=14, pady=(0, 8))

        # Поле ввода нового проекта (скрыто по умолчанию)
        self._new_project_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        self._entry_new_project = ctk.CTkEntry(
            self._new_project_frame, placeholder_text="Название проекта",
            width=200, height=34, fg_color=BG_MAIN, text_color=TEXT,
            border_color=BORDER, border_width=1,
            placeholder_text_color=MUTED,
        )
        self._entry_new_project.pack(side="left", padx=(14, 4))
        self._entry_new_project.bind("<Return>", lambda e: self._confirm_new_project())

        ctk.CTkButton(
            self._new_project_frame, text="✓", width=34, height=34,
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=6,
            command=self._confirm_new_project,
        ).pack(side="left", padx=(0, 14))

        # --- Этап ---
        ctk.CTkLabel(
            input_card, text="ЭТАП",
            font=("Segoe UI", 9), text_color=MUTED,
        ).pack(padx=14, pady=(4, 2), anchor="w")

        self._stage_var = ctk.StringVar()
        self._stage_menu = ctk.CTkOptionMenu(
            input_card, variable=self._stage_var,
            values=[], width=250, height=36,
            fg_color=BG_MAIN, text_color=TEXT,
            button_color=BORDER, button_hover_color=HOVER,
            dropdown_fg_color=BG_CARD, dropdown_text_color=TEXT,
            dropdown_hover_color=HOVER,
            command=self._on_stage_selected,
        )
        self._stage_menu.pack(padx=14, pady=(0, 8))

        # Поле ввода нового этапа (скрыто по умолчанию)
        self._new_stage_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        self._entry_new_stage = ctk.CTkEntry(
            self._new_stage_frame, placeholder_text="Название этапа",
            width=200, height=34, fg_color=BG_MAIN, text_color=TEXT,
            border_color=BORDER, border_width=1,
            placeholder_text_color=MUTED,
        )
        self._entry_new_stage.pack(side="left", padx=(14, 4))
        self._entry_new_stage.bind("<Return>", lambda e: self._confirm_new_stage())

        ctk.CTkButton(
            self._new_stage_frame, text="✓", width=34, height=34,
            fg_color=ACCENT, hover_color="#25a385",
            text_color="#0d0f0d", corner_radius=6,
            command=self._confirm_new_stage,
        ).pack(side="left", padx=(0, 14))

        # Загружаем данные
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
```

- [ ] **Step 3: Add dropdown logic methods**

Remove old methods `_on_entry_change()` and `_select_project()`. Add these new methods:

```python
    # --- Dropdown logic ---

    def _load_projects_dropdown(self):
        """Загружает список проектов в dropdown. Выбирает последний использованный."""
        projects = get_projects_sorted()
        values = ["➕ Новый проект..."] + projects

        self._project_menu.configure(values=values)

        # Выбираем последний проект по умолчанию
        last = get_last_session_info()
        if last and last[0] in projects:
            self._project_var.set(last[0])
            self._load_stages_dropdown(last[0], default_stage=last[1])
        elif projects:
            self._project_var.set(projects[0])
            self._load_stages_dropdown(projects[0])
        else:
            self._project_var.set("➕ Новый проект...")
            self._on_project_selected("➕ Новый проект...")

    def _load_stages_dropdown(self, project_name: str, default_stage: str | None = None):
        """Загружает этапы выбранного проекта."""
        project_id = get_or_create_project(project_name)
        stages = get_stages(project_id)
        values = ["➕ Новый этап..."] + stages

        self._stage_menu.configure(values=values)

        if default_stage and default_stage in stages:
            self._stage_var.set(default_stage)
        elif stages:
            self._stage_var.set(stages[0])

    def _on_project_selected(self, choice: str):
        """Обработчик выбора проекта."""
        self._new_project_frame.pack_forget()
        self._new_stage_frame.pack_forget()

        if choice == "➕ Новый проект...":
            self._new_project_frame.pack(fill="x", pady=(0, 8))
            self._entry_new_project.delete(0, "end")
            self._entry_new_project.focus()
            self._stage_menu.configure(values=[])
            self._stage_var.set("")
        else:
            self._load_stages_dropdown(choice)

    def _on_stage_selected(self, choice: str):
        """Обработчик выбора этапа."""
        self._new_stage_frame.pack_forget()

        if choice == "➕ Новый этап...":
            self._new_stage_frame.pack(fill="x", pady=(0, 8))
            self._entry_new_stage.delete(0, "end")
            self._entry_new_stage.focus()

    def _confirm_new_project(self):
        """Создаёт новый проект и обновляет dropdown."""
        name = self._entry_new_project.get().strip()
        if not name:
            return

        project_id = get_or_create_project(name)
        # Создаём этап "Общее" по умолчанию
        from db import get_or_create_stage
        get_or_create_stage(project_id, "Общее")

        self._new_project_frame.pack_forget()
        self._load_projects_dropdown()
        self._project_var.set(name)
        self._load_stages_dropdown(name)

    def _confirm_new_stage(self):
        """Создаёт новый этап и обновляет dropdown."""
        name = self._entry_new_stage.get().strip()
        if not name:
            return

        project_name = self._project_var.get()
        if not project_name or project_name == "➕ Новый проект...":
            return

        project_id = get_or_create_project(project_name)
        from db import get_or_create_stage
        get_or_create_stage(project_id, name)

        self._new_stage_frame.pack_forget()
        self._load_stages_dropdown(project_name)
        self._stage_var.set(name)
```

- [ ] **Step 4: Update _start_work() to use dropdowns**

Replace the `_start_work()` method:

```python
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
```

- [ ] **Step 5: Update _render_state() to show project + stage**

In the working state, show both project and stage name:

```python
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
```

- [ ] **Step 6: Update _stop_work() — remove old entry clearing**

In `_stop_work()`, remove the line `self._entry_project.delete(0, "end")` since the text entry no longer exists:

```python
    def _stop_work(self):
        """Завершает текущую сессию."""
        if self.app_state.session_id is None:
            return

        if self.app_state.pause_id is not None:
            end_pause(self.app_state.pause_id)

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
```

- [ ] **Step 7: Run app and verify dropdowns work**

Run: `cd C:/Users/User/GeserFlow && python main.py`
Expected: Main window shows project dropdown and stage dropdown. Selecting "Новый проект..." shows input field. Creating projects creates "Общее" stage. Switching projects updates stages list.

- [ ] **Step 8: Commit**

```bash
git add ui/main_window.py
git commit -m "feat(ui): replace text input with project/stage dropdowns"
```

---

### Task 5: Dashboard — project rows with expandable stages

**Files:**
- Modify: `ui/dashboard_window.py`

- [ ] **Step 1: Update imports**

```python
from db import get_stats_range, get_daily_totals, get_projects, get_projects_with_stages_stats
```

- [ ] **Step 2: Replace _render_table() with project-level rows**

Replace the entire `_render_table()` method. The new version shows one row per project with a "▼" button, and expands to show stages on click:

```python
    def _render_table(self):
        """Перерисовывает таблицу: проекты с раскрываемыми этапами."""
        for w in self._rows_container.winfo_children():
            w.destroy()

        self._expanded: set[str] = getattr(self, "_expanded", set())

        d_from = self._date_from_var.get()
        d_to = self._date_to_var.get()
        project_filter = self._project_var.get()
        if project_filter != "Все проекты":
            # Filter: show only matching project in the aggregated view
            pass

        projects_data = get_projects_with_stages_stats(d_from, d_to)

        if project_filter != "Все проекты":
            projects_data = [p for p in projects_data if p["project_name"] == project_filter]

        col_widths = [160, 75, 65, 65, 50, 40]
        total_work = 0
        total_pause = 0
        total_sessions = 0

        for idx, proj in enumerate(projects_data):
            bg = BG_ROW_ALT if idx % 2 == 0 else BG_MAIN
            proj_name = proj["project_name"]
            work_s = proj["work_seconds"]
            pause_s = proj["pause_seconds"]
            break_s = proj["break_seconds"]
            sess_count = proj["session_count"]
            total_work += work_s
            total_pause += pause_s
            total_sessions += sess_count

            is_expanded = proj_name in self._expanded

            # Project row
            row_frame = ctk.CTkFrame(self._rows_container, fg_color=bg, height=30)
            row_frame.pack(fill="x", pady=0)
            row_frame.pack_propagate(False)

            # Expand button
            expand_text = "▲" if is_expanded else "▼"
            btn_expand = ctk.CTkButton(
                row_frame, text=expand_text, width=30, height=26,
                fg_color="transparent", hover_color="#333333",
                text_color=MUTED, font=("Segoe UI", 10),
                command=lambda pn=proj_name: self._toggle_expand(pn),
            )
            btn_expand.pack(side="left", padx=(2, 0))

            values = [
                proj_name,
                _fmt_hm(work_s),
                _fmt_hm(pause_s),
                _fmt_hm(break_s),
                str(sess_count),
            ]

            for i, val in enumerate(values):
                ctk.CTkLabel(
                    row_frame, text=val, width=col_widths[i],
                    font=("Segoe UI", 11, "bold" if i == 0 else ""),
                    text_color=TEXT, anchor="w",
                ).pack(side="left", padx=1)

            # Double-click to expand
            row_frame.bind("<Double-Button-1>", lambda e, pn=proj_name: self._toggle_expand(pn))

            # Stage sub-rows (if expanded)
            if is_expanded:
                for stage in proj["stages"]:
                    stage_frame = ctk.CTkFrame(self._rows_container, fg_color="#1e221e", height=26)
                    stage_frame.pack(fill="x", pady=0)
                    stage_frame.pack_propagate(False)

                    # Indent
                    ctk.CTkLabel(stage_frame, text="", width=30).pack(side="left")

                    stage_values = [
                        f"  {stage['stage_name']}",
                        _fmt_hm(stage["work_seconds"]),
                        _fmt_hm(stage["pause_seconds"]),
                        _fmt_hm(stage["break_seconds"]),
                        str(stage["session_count"]),
                    ]

                    for i, val in enumerate(stage_values):
                        ctk.CTkLabel(
                            stage_frame, text=val, width=col_widths[i],
                            font=("Segoe UI", 10),
                            text_color=MUTED if i == 0 else TEXT, anchor="w",
                        ).pack(side="left", padx=1)

        count = total_sessions
        self._lbl_totals.configure(
            text=f"Сессий: {count}  |  Рабочих часов: {_fmt_hm(total_work)}  |  Пауз: {_fmt_hm(total_pause)}"
        )
```

- [ ] **Step 3: Add _toggle_expand() method**

```python
    def _toggle_expand(self, project_name: str):
        """Раскрывает/сворачивает этапы проекта."""
        if not hasattr(self, "_expanded"):
            self._expanded = set()
        if project_name in self._expanded:
            self._expanded.discard(project_name)
        else:
            self._expanded.add(project_name)
        self._render_table()
```

- [ ] **Step 4: Update table header columns**

Replace the old columns definition and header rendering:

```python
        self._columns = ["Проект", "Работа", "Паузы", "Перекуры", "Сессий"]
        self._col_keys = ["project_name", "work_seconds", "pause_seconds", "break_seconds", "session_count"]

        header_row = ctk.CTkFrame(self._table_frame, fg_color=HEADER_BG, height=30)
        header_row.pack(fill="x", pady=(0, 2))
        header_row.pack_propagate(False)

        # Space for expand button
        ctk.CTkLabel(header_row, text="", width=30).pack(side="left")

        col_widths = [160, 75, 65, 65, 50]
        for i, col_name in enumerate(self._columns):
            ctk.CTkLabel(
                header_row, text=col_name, width=col_widths[i],
                fg_color="transparent",
                text_color=MUTED, font=("Segoe UI", 11, "bold"),
                anchor="w",
            ).pack(side="left", padx=1)
```

- [ ] **Step 5: Update _refresh() — remove sort logic since table is now project-level**

```python
    def _refresh(self):
        """Обновляет таблицу и итоги."""
        project_list = ["Все проекты"] + get_projects()
        self._project_menu.configure(values=project_list)
        self._update_summary_cards()
        self._render_table()
```

- [ ] **Step 6: Remove _sort_by() method**

Delete the `_sort_by()` method entirely — sorting is no longer needed for the project-level view.

- [ ] **Step 7: Update _export_csv() to include stage column**

```python
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
                writer.writerow(["Дата", "Проект", "Этап", "Начало", "Конец",
                                 "Работа (сек)", "Паузы (сек)", "Перекуры (сек)"])
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
```

- [ ] **Step 8: Run app and verify dashboard**

Run: `cd C:/Users/User/GeserFlow && python main.py`
Expected: Dashboard shows project rows. Clicking "▼" or double-clicking expands stages. Stages show in creation order. Collapsing works.

- [ ] **Step 9: Commit**

```bash
git add ui/dashboard_window.py
git commit -m "feat(dashboard): project rows with expandable stage sub-rows"
```

---

### Task 6: Integration — update interrupted session dialog

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Update interrupted session dialog text**

In `app.py`, `_check_interrupted()`, update the label to show stage name:

```python
        project = session["project_name"]
        stage = session.get("stage_name", "")
        start = session["start_time"]
        sid = session["id"]

        display = f'"{project}"'
        if stage and stage != "Общее":
            display += f' → {stage}'

        ctk.CTkLabel(
            dialog,
            text=f'Найдена незавершённая сессия:\n{display}, начата в {start}.\nЗавершить её?',
            font=("Segoe UI", 13), text_color="#e0e0e0",
            wraplength=340, justify="center",
        ).pack(pady=(18, 12))
```

- [ ] **Step 2: Run full app test**

Run: `cd C:/Users/User/GeserFlow && python main.py`
Expected: Full flow works — select project, select stage, start work, stop work, check dashboard with expanded stages.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): show stage in interrupted session dialog"
```
