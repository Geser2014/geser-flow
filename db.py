"""
Работа с SQLite базой данных.
Все операции с БД — только через этот модуль.
"""

import sqlite3
import os
from datetime import datetime, timedelta

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "geserflow.db")


def _connect() -> sqlite3.Connection:
    """Создаёт подключение с row_factory."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
            conn.execute("INSERT INTO stages (project_id, name) VALUES (?, ?)", (row[0], "Общее"))
        conn.commit()

        # Migration: assign stage_id to sessions that don't have one
        conn.execute("""
            UPDATE sessions SET stage_id = (
                SELECT st.id FROM stages st
                WHERE st.project_id = sessions.project_id AND st.name = 'Общее'
            ) WHERE stage_id IS NULL
        """)
        conn.commit()
    finally:
        conn.close()


def get_or_create_project(name: str) -> int:
    """Возвращает id проекта, создаёт если не существует."""
    conn = _connect()
    try:
        row = conn.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute("INSERT INTO projects (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_projects() -> list[str]:
    """Список всех проектов."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT name FROM projects ORDER BY name").fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


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


def get_stages(project_id: int) -> list[str]:
    """Этапы проекта, отсортированные по последней активности сессий (новые первые)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT st.name
               FROM stages st
               LEFT JOIN sessions s ON s.stage_id = st.id AND s.status != 'active'
               WHERE st.project_id = ?
               GROUP BY st.id
               ORDER BY MAX(s.end_time) DESC NULLS LAST""",
            (project_id,),
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


def get_projects_sorted() -> list[str]:
    """Проекты, отсортированные по последней активности сессий (новые первые)."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT p.name
               FROM projects p
               LEFT JOIN sessions s ON s.project_id = p.id AND s.status != 'active'
               GROUP BY p.id
               ORDER BY MAX(s.end_time) DESC NULLS LAST"""
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


def get_last_session_info() -> tuple[str, str] | None:
    """Возвращает (project_name, stage_name) последней завершённой сессии."""
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT p.name as project_name, st.name as stage_name
               FROM sessions s
               JOIN projects p ON p.id = s.project_id
               LEFT JOIN stages st ON st.id = s.stage_id
               WHERE s.status = 'completed'
               ORDER BY s.end_time DESC
               LIMIT 1"""
        ).fetchone()
        if row:
            return (row["project_name"], row["stage_name"])
        return None
    finally:
        conn.close()


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


def end_session(session_id: int, work_sec: int, pause_sec: int, break_sec: int) -> None:
    """Завершает сессию с итоговыми значениями."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    try:
        conn.execute(
            """UPDATE sessions
               SET end_time = ?, work_seconds = ?, pause_seconds = ?,
                   break_seconds = ?, status = 'completed'
               WHERE id = ?""",
            (now, work_sec, pause_sec, break_sec, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def start_pause(session_id: int, pause_type: str) -> int:
    """Начинает паузу, возвращает pause_id."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO pauses (session_id, start_time, type) VALUES (?, ?, ?)",
            (session_id, now, pause_type),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def end_pause(pause_id: int) -> None:
    """Завершает паузу."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    try:
        conn.execute("UPDATE pauses SET end_time = ? WHERE id = ?", (now, pause_id))
        conn.commit()
    finally:
        conn.close()


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


def mark_interrupted(session_id: int) -> None:
    """Помечает сессию как прерванную."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    try:
        conn.execute(
            "UPDATE sessions SET status = 'interrupted', end_time = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_session(session_id: int) -> None:
    """Удаляет сессию и связанные паузы."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM pauses WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def delete_stage(stage_id: int) -> None:
    """Удаляет этап и все его сессии (с паузами)."""
    conn = _connect()
    try:
        # Get all sessions for this stage
        sessions = conn.execute(
            "SELECT id FROM sessions WHERE stage_id = ?", (stage_id,)
        ).fetchall()
        for s in sessions:
            conn.execute("DELETE FROM pauses WHERE session_id = ?", (s["id"],))
            conn.execute("DELETE FROM sessions WHERE id = ?", (s["id"],))
        conn.execute("DELETE FROM stages WHERE id = ?", (stage_id,))
        conn.commit()
    finally:
        conn.close()


def delete_project(project_id: int) -> None:
    """Удаляет проект, все его этапы и сессии (с паузами)."""
    conn = _connect()
    try:
        # Get all sessions for this project
        sessions = conn.execute(
            "SELECT id FROM sessions WHERE project_id = ?", (project_id,)
        ).fetchall()
        for s in sessions:
            conn.execute("DELETE FROM pauses WHERE session_id = ?", (s["id"],))
            conn.execute("DELETE FROM sessions WHERE id = ?", (s["id"],))
        conn.execute("DELETE FROM stages WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    finally:
        conn.close()


def get_project_id_by_name(name: str) -> int | None:
    """Возвращает id проекта по имени."""
    conn = _connect()
    try:
        row = conn.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_stage_id(project_id: int, stage_name: str) -> int | None:
    """Возвращает id этапа по имени и проекту."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT id FROM stages WHERE project_id = ? AND name = ?",
            (project_id, stage_name),
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_stats_today() -> dict:
    """Статистика за сегодня: work_seconds, pause_seconds, break_seconds, session_count."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _connect()
    try:
        row = conn.execute(
            """SELECT
                 COALESCE(SUM(work_seconds), 0) as work_seconds,
                 COALESCE(SUM(pause_seconds), 0) as pause_seconds,
                 COALESCE(SUM(break_seconds), 0) as break_seconds,
                 COUNT(*) as session_count
               FROM sessions
               WHERE date(start_time) = ? AND status != 'active'""",
            (today,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


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


def get_projects_with_stages_stats(date_from: str, date_to: str) -> list[dict]:
    """Проекты с агрегированной статистикой и вложенными этапами за период."""
    conn = _connect()
    try:
        # Get per-stage stats
        stage_rows = conn.execute(
            """SELECT p.id as project_id, p.name as project_name,
                      st.id as stage_id, st.name as stage_name,
                      COALESCE(SUM(s.work_seconds), 0) as work_seconds,
                      COALESCE(SUM(s.pause_seconds), 0) as pause_seconds,
                      COALESCE(SUM(s.break_seconds), 0) as break_seconds,
                      COUNT(s.id) as session_count
               FROM projects p
               JOIN stages st ON st.project_id = p.id
               LEFT JOIN sessions s ON s.stage_id = st.id
                   AND date(s.start_time) >= ? AND date(s.start_time) <= ?
                   AND s.status != 'active'
               GROUP BY p.id, st.id
               ORDER BY p.name ASC, st.created_at ASC""",
            (date_from, date_to),
        ).fetchall()

        projects: dict[int, dict] = {}
        for r in stage_rows:
            pid = r["project_id"]
            if pid not in projects:
                projects[pid] = {
                    "project_name": r["project_name"],
                    "work_seconds": 0,
                    "pause_seconds": 0,
                    "break_seconds": 0,
                    "session_count": 0,
                    "stages": [],
                }
            stage_dict = {
                "stage_name": r["stage_name"],
                "work_seconds": r["work_seconds"],
                "pause_seconds": r["pause_seconds"],
                "break_seconds": r["break_seconds"],
                "session_count": r["session_count"],
            }
            projects[pid]["stages"].append(stage_dict)
            projects[pid]["work_seconds"] += r["work_seconds"]
            projects[pid]["pause_seconds"] += r["pause_seconds"]
            projects[pid]["break_seconds"] += r["break_seconds"]
            projects[pid]["session_count"] += r["session_count"]

        return list(projects.values())
    finally:
        conn.close()


def get_daily_totals(date_from: str, date_to: str, project_name: str | None = None) -> list[dict]:
    """Суммы по дням за период."""
    conn = _connect()
    try:
        query = """
            SELECT date(s.start_time) as day,
                   COALESCE(SUM(s.work_seconds), 0) as work_seconds,
                   COALESCE(SUM(s.pause_seconds), 0) as pause_seconds,
                   COALESCE(SUM(s.break_seconds), 0) as break_seconds,
                   COUNT(*) as session_count
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
            WHERE date(s.start_time) >= ? AND date(s.start_time) <= ?
              AND s.status != 'active'
        """
        params: list = [date_from, date_to]
        if project_name:
            query += " AND p.name = ?"
            params.append(project_name)
        query += " GROUP BY date(s.start_time) ORDER BY day DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_projects_with_totals() -> list[dict]:
    """Все проекты с суммарным временем."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT p.name,
                      COALESCE(SUM(s.work_seconds), 0) as total_work_seconds,
                      COUNT(s.id) as session_count
               FROM projects p
               LEFT JOIN sessions s ON s.project_id = p.id AND s.status != 'active'
               GROUP BY p.id
               ORDER BY total_work_seconds DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_daily_history(date_from: str, date_to: str) -> list[dict]:
    """История по дням: работа, паузы, сессии, начало/конец дня, топ-проект, топ-этап."""
    conn = _connect()
    try:
        days = conn.execute(
            """SELECT date(s.start_time) as day,
                      MIN(time(s.start_time)) as first_start,
                      MAX(time(COALESCE(s.end_time, s.start_time))) as last_end,
                      COALESCE(SUM(s.work_seconds), 0) as work_seconds,
                      COALESCE(SUM(s.pause_seconds), 0) as pause_seconds,
                      COUNT(*) as session_count
               FROM sessions s
               WHERE date(s.start_time) >= ? AND date(s.start_time) <= ?
                 AND s.status != 'active'
               GROUP BY date(s.start_time)
               ORDER BY day DESC""",
            (date_from, date_to),
        ).fetchall()

        result = []
        for d in days:
            day = d["day"]

            top_proj = conn.execute(
                """SELECT p.name, SUM(s.work_seconds) as total
                   FROM sessions s JOIN projects p ON p.id = s.project_id
                   WHERE date(s.start_time) = ? AND s.status != 'active'
                   GROUP BY p.id ORDER BY total DESC LIMIT 1""",
                (day,),
            ).fetchone()

            top_stage = conn.execute(
                """SELECT st.name, SUM(s.work_seconds) as total
                   FROM sessions s JOIN stages st ON st.id = s.stage_id
                   WHERE date(s.start_time) = ? AND s.status != 'active'
                   GROUP BY st.id ORDER BY total DESC LIMIT 1""",
                (day,),
            ).fetchone()

            result.append({
                "day": day,
                "first_start": d["first_start"][:5],
                "last_end": d["last_end"][:5],
                "work_seconds": d["work_seconds"],
                "pause_seconds": d["pause_seconds"],
                "session_count": d["session_count"],
                "top_project": top_proj["name"] if top_proj else "",
                "top_stage": top_stage["name"] if top_stage else "",
            })

        return result
    finally:
        conn.close()
