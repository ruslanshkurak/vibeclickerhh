import sqlite3
import sys
import datetime
from pathlib import Path

# Путь к БД: рядом с EXE (frozen) или в корне проекта (dev-режим)
if getattr(sys, 'frozen', False):
    _BASE = Path(sys.executable).parent
else:
    _BASE = Path(__file__).resolve().parent.parent

DB_PATH = _BASE / "analytics.db"

class Database:
    @staticmethod
    def _get_connection():
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        return conn

    @staticmethod
    def init_db():
        with Database._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT (datetime('now', 'localtime')),
                    job_id TEXT UNIQUE,
                    title TEXT,
                    company TEXT,
                    url TEXT,
                    ai_score INTEGER,
                    ai_reason TEXT,
                    cover_letter TEXT,
                    status TEXT
                )
            ''')
            
            # Миграции схемы (добавление новых колонок)
            try:
                cursor.execute("ALTER TABLE applications ADD COLUMN interview_status TEXT DEFAULT 'Ожидание'")
            except sqlite3.OperationalError:
                pass # Колонка уже существует
                
            try:
                cursor.execute("ALTER TABLE applications ADD COLUMN user_notes TEXT DEFAULT ''")
            except sqlite3.OperationalError:
                pass # Колонка уже существует

            # Таблица сессий работы бота для аналитики времени
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME DEFAULT (datetime('now', 'localtime')),
                    end_time DATETIME,
                    duration_seconds INTEGER DEFAULT 0
                )
            ''')
                
            # Таблица состояния бота (ключ-значение)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
                
            conn.commit()

    @staticmethod
    def update_interview_status(job_id: str, status: str):
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE applications SET interview_status = ? WHERE job_id = ?", (status, job_id))
                conn.commit()
        except Exception as e:
            print(f"Ошибка при обновлении статуса: {e}")

    @staticmethod
    def update_user_notes(job_id: str, notes: str):
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE applications SET user_notes = ? WHERE job_id = ?", (notes, job_id))
                conn.commit()
        except Exception as e:
            print(f"Ошибка при обновлении заметок: {e}")

    @staticmethod
    def update_bot_status(job_id: str, status: str):
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE applications SET status = ? WHERE job_id = ?", (status, job_id))
                conn.commit()
        except Exception as e:
            print(f"Ошибка при обновлении статуса бота: {e}")

    @staticmethod
    def get_successful_applies_count() -> int:
        """
        Возвращает количество успешных откликов в базе данных.
        Успешными считаются те, у которых статус начинается с 'Успешно'.
        """
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'Успешно отправлено'")
                res = cursor.fetchone()
                return res[0] if res and res[0] is not None else 0
        except Exception as e:
            print(f"Ошибка при получении количества успешных откликов: {e}")
            return 0

    @staticmethod
    def log_vacancy(job_id, title="", company="", url="", ai_score=None, ai_reason="", cover_letter="", status=""):
        """
        Сохраняет или обновляет запись о вакансии в базе данных.
        """
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO applications (job_id, title, company, url, ai_score, ai_reason, cover_letter, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_id) DO UPDATE SET
                        title=excluded.title,
                        company=excluded.company,
                        url=excluded.url,
                        ai_score=excluded.ai_score,
                        ai_reason=excluded.ai_reason,
                        cover_letter=excluded.cover_letter,
                        status=excluded.status,
                        timestamp=datetime('now', 'localtime')
                ''', (job_id, title, company, url, ai_score, ai_reason, cover_letter, status))
                conn.commit()
        except Exception as e:
            print(f"[⚠️ Ошибка БД] Не удалось сохранить вакансию {job_id}: {e}")

    @staticmethod
    def delete_vacancy(job_id: str):
        """Удаляет вакансию из БД."""
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM applications WHERE job_id = ?", (job_id,))
                conn.commit()
        except Exception as e:
            print(f"Ошибка при удалении вакансии: {e}")

    @staticmethod
    def is_already_applied(job_id: str) -> bool:
        """
        Проверяет, есть ли вакансия в БД. 
        """
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM applications WHERE job_id = ?", (job_id,))
                return cursor.fetchone() is not None
        except Exception:
            return False

    @staticmethod
    def get_all_records():
        """
        Возвращает все записи для дашборда.
        """
        try:
            with Database._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM applications ORDER BY timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Ошибка при получении записей из БД: {e}")
            return []

    @staticmethod
    def start_session() -> int:
        """Создает новую сессию работы бота и возвращает её ID."""
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO bot_sessions (start_time, duration_seconds) VALUES (datetime('now', 'localtime'), 0)"
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Ошибка при создании сессии в БД: {e}")
            return 0

    @staticmethod
    def update_session_duration(session_id: int, duration_seconds: int):
        """Обновляет текущую продолжительность сессии."""
        if not session_id:
            return
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE bot_sessions SET duration_seconds = ? WHERE id = ?",
                    (duration_seconds, session_id)
                )
                conn.commit()
        except Exception as e:
            print(f"Ошибка при обновлении длительности сессии: {e}")

    @staticmethod
    def end_session(session_id: int, duration_seconds: int):
        """Завершает сессию работы бота, фиксируя финальное время."""
        if not session_id:
            return
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE bot_sessions SET end_time = datetime('now', 'localtime'), duration_seconds = ? WHERE id = ?",
                    (duration_seconds, session_id)
                )
                conn.commit()
        except Exception as e:
            print(f"Ошибка при завершении сессии в БД: {e}")

    @staticmethod
    def get_total_duration() -> int:
        """Возвращает суммарное время работы бота в секундах."""
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(duration_seconds) FROM bot_sessions")
                res = cursor.fetchone()
                return res[0] if res and res[0] is not None else 0
        except Exception as e:
            print(f"Ошибка при получении суммарного времени работы: {e}")
            return 0

    @staticmethod
    def get_state(key: str, default: str = "") -> str:
        """Возвращает значение из таблицы bot_state."""
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM bot_state WHERE key = ?", (key,))
                res = cursor.fetchone()
                return res[0] if res and res[0] is not None else default
        except Exception:
            return default

    @staticmethod
    def set_state(key: str, value: str):
        """Сохраняет или обновляет значение в таблице bot_state."""
        try:
            with Database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO bot_state (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                ''', (key, str(value)))
                conn.commit()
        except Exception as e:
            print(f"Ошибка при сохранении состояния в БД ({key}): {e}")

