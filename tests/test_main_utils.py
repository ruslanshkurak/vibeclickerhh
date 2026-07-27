import pytest
from main import extract_job_id, get_smart_dynamic_delay

def test_extract_job_id():
    """Проверка извлечения ID вакансий из различных форматов URL hh.ru."""
    assert extract_job_id("https://hh.ru/vacancy/11223344") == "11223344"
    assert extract_job_id("https://hh.ru/vacancy/99887766?query=python&area=1") == "99887766"
    assert extract_job_id("http://spb.hh.ru/vacancy/55443322/") == "55443322"
    assert extract_job_id("invalid_url_without_id") == ""

def test_smart_dynamic_delay_range():
    """Проверка генерации задержек."""
    # Обычный шаг
    delay, msg = get_smart_dynamic_delay(apply_count=1)
    assert delay >= 18.0
    assert "Динамическое ожидание" in msg
