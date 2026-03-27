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

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id),
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


def start_session(project_name: str) -> int:
    """Начинает новую сессию, возвращает session_id."""
    project_id = get_or_create_project(project_name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO sessions (project_id, start_time, status) VALUES (?, ?, 'active')",
            (project_id, now),
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
            """SELECT s.id, s.start_time, s.work_seconds, p.name as project_name
               FROM sessions s
               JOIN projects p ON p.id = s.project_id
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
            SELECT s.id, p.name as project_name, s.start_time, s.end_time,
                   s.work_seconds, s.pause_seconds, s.break_seconds, s.status
            FROM sessions s
            JOIN projects p ON p.id = s.project_id
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
