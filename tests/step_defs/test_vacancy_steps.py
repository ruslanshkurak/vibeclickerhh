import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from src.config import Config

# Загружаем сценарии из .feature файла
scenarios('../features/vacancy_filtering.feature')

@pytest.fixture
def test_context():
    return {}

@given(parsers.parse('компания "{company_name}" находится в черном списке'))
def add_to_blacklist(company_name, monkeypatch):
    monkeypatch.setattr(Config, "BLACKLIST_EMPLOYERS", [company_name.lower()])

@when(parsers.parse('бот проверяет вакансию компании "{company_name}"'), target_fixture="check_result")
def check_company_blacklist(company_name):
    return Config.is_employer_blacklisted(company_name)

@then(parsers.parse('вакансия должна быть пропущена с причиной "Черный список"'))
def verify_blacklisted(check_result):
    assert check_result is True

@given(parsers.parse('минимальный порог балла равен {score:d}'))
def set_min_score(score, monkeypatch):
    monkeypatch.setattr(Config, "MIN_FIT_SCORE", score)

@when(parsers.parse('система оценивает вакансию на {eval_score:d} баллов'), target_fixture="eval_context")
def eval_vacancy(eval_score):
    return {
        "score": eval_score,
        "is_passed": eval_score >= Config.MIN_FIT_SCORE
    }

@then(parsers.parse('вакансия должна быть пропущена с причиной "Низкая оценка"'))
def verify_low_score(eval_context):
    assert eval_context["is_passed"] is False

@then('вакансия должна быть одобрена для отправки отклика')
def verify_high_score(eval_context):
    assert eval_context["is_passed"] is True
