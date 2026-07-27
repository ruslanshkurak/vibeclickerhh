import os
import sys
import tempfile
import sqlite3
from pathlib import Path
import pytest

# Гарантируем, что корень проекта находится в sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import Config
from src.database import Database, DB_PATH

@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """
    Фикстура для создания чистой временной базы данных SQLite для каждого теста.
    Гарантирует изоляцию от боевой базы данных analytics.db.
    """
    test_db_path = tmp_path / "test_analytics.db"
    monkeypatch.setattr("src.database.DB_PATH", test_db_path)
    
    # Инициализируем схему во временной БД
    Database.init_db()
    
    yield test_db_path
    
    # Очистка после выполнения теста
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except Exception:
            pass

@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """
    Фикстура для изоляции файлов конфигурации (resume.txt, session.json, .env).
    """
    temp_resume = tmp_path / "resume.txt"
    temp_session = tmp_path / "session.json"
    temp_applied = tmp_path / "applied_jobs.txt"
    
    monkeypatch.setattr(Config, "RESUME_FILE", temp_resume)
    monkeypatch.setattr(Config, "SESSION_FILE", temp_session)
    monkeypatch.setattr(Config, "APPLIED_LOG_FILE", temp_applied)
    
    return {
        "resume_file": temp_resume,
        "session_file": temp_session,
        "applied_file": temp_applied
    }
