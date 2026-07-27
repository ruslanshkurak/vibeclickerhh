import pytest
from src.database import Database

def test_database_initialization(temp_db):
    """Проверка создания таблиц в изолированной БД."""
    assert temp_db.exists()
    records = Database.get_all_records()
    assert isinstance(records, list)
    assert len(records) == 0

def test_log_and_retrieve_vacancy(temp_db):
    """Проверка сохранения и извлечения записи о вакансии."""
    job_id = "12345678"
    Database.log_vacancy(
        job_id=job_id,
        title="Python Senior Engineer",
        company="Tech Corp",
        url="https://hh.ru/vacancy/12345678",
        ai_score=9,
        ai_reason="Отличное совпадение стека",
        cover_letter="Здравствуйте! Меня заинтересовала ваша вакансия...",
        status="Успешно отправлено"
    )
    
    assert Database.is_already_applied(job_id) is True
    assert Database.get_successful_applies_count() == 1
    
    records = Database.get_all_records()
    assert len(records) == 1
    rec = records[0]
    assert rec["job_id"] == job_id
    assert rec["title"] == "Python Senior Engineer"
    assert rec["company"] == "Tech Corp"
    assert rec["ai_score"] == 9

def test_update_bot_status_and_notes(temp_db):
    """Проверка обновления статуса бота и заметок пользователя."""
    job_id = "87654321"
    Database.log_vacancy(job_id=job_id, title="Go Developer", company="Inno", status="Пропущено (Низкая оценка)")
    
    Database.update_bot_status(job_id, "Успешно отправлено")
    Database.update_user_notes(job_id, "Пригласили на интервью на пятницу")
    Database.update_interview_status(job_id, "Приглашение")
    
    records = Database.get_all_records()
    rec = [r for r in records if r["job_id"] == job_id][0]
    assert rec["status"] == "Успешно отправлено"
    assert rec["user_notes"] == "Пригласили на интервью на пятницу"
    assert rec["interview_status"] == "Приглашение"

def test_session_lifecycle(temp_db):
    """Проверка жизненного цикла сессий работы бота."""
    session_id = Database.start_session()
    assert session_id > 0
    
    Database.update_session_duration(session_id, 120)
    assert Database.get_total_duration() == 120
    
    Database.end_session(session_id, 300)
    assert Database.get_total_duration() == 300
