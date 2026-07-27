import pytest
from src.config import Config

def test_safe_int_conversion():
    """Проверка безопасностей конвертации строк в числа."""
    assert Config._safe_int("10", 0) == 10
    assert Config._safe_int("  25  ", 0) == 25
    assert Config._safe_int(None, 5) == 5
    assert Config._safe_int("", 7) == 0
    assert Config._safe_int("invalid_string", 3) == 3

def test_is_employer_blacklisted(monkeypatch):
    """Проверка работы черного списка работодателей."""
    monkeypatch.setattr(Config, "BLACKLIST_EMPLOYERS", ["рога и копыта", "scam inc", "вектор"])
    
    assert Config.is_employer_blacklisted("ООО Рога и Копыта") is True
    assert Config.is_employer_blacklisted("Scam Inc Ltd") is True
    assert Config.is_employer_blacklisted("Вектор ИТ") is True
    assert Config.is_employer_blacklisted("Яндекс") is False
    assert Config.is_employer_blacklisted("") is False

def test_get_resume_when_file_missing(isolated_config):
    """Проверка get_resume() когда файл резюме отсутствует."""
    resume_file = isolated_config["resume_file"]
    if resume_file.exists():
        resume_file.unlink()
        
    resume_text = Config.get_resume()
    assert resume_text == ""

def test_get_resume_with_custom_content(isolated_config):
    """Проверка get_resume() с заполненным текстом."""
    resume_file = isolated_config["resume_file"]
    valid_resume = "Опыт работы: 5 лет Python Developer. Стек: FastAPI, PostgreSQL, Docker."
    resume_file.write_text(valid_resume, encoding="utf-8")
    
    assert Config.get_resume() == valid_resume
