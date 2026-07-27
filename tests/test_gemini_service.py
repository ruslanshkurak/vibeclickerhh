import pytest
from src.gemini_service import GeminiService
from src.config import Config

def test_gemini_service_uninitialized_fallback(monkeypatch):
    """Проверка работы GeminiService когда API-ключ отсутствует."""
    monkeypatch.setattr(Config, "GEMINI_API_KEY", "")
    
    service = GeminiService()
    assert service.initialized is False
    
    # При необработанном ключе оценка возвращает 10 (авто-одобрение)
    eval_result = service.evaluate_vacancy("Резюме", "Текст вакансии")
    assert eval_result["score"] == 10
    assert "Авто-оценка отключена" in eval_result["reason"]
    
    # Генерация письма возвращает дефолтный вежливый шаблон
    letter = service.generate_cover_letter("Резюме", "Текст вакансии")
    assert "Здравствуйте!" in letter
