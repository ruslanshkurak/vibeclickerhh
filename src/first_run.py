"""
first_run.py — Инициализация при первом запуске VibeClickerHH.ru.
Создаёт шаблонные файлы конфигурации рядом с .exe (или в папке скрипта),
если они ещё не существуют. Ваши реальные данные NOT включены в билд.
"""
from pathlib import Path

# ─── Шаблон .env (все ключи пустые — пользователь заполняет сам) ───
_ENV_TEMPLATE = """\
# VibeClickerHH.ru — Файл конфигурации
# Заполните поля ниже перед первым запуском бота

# ── Обязательно ──────────────────────────────────────────────────────
# API Ключ от Google AI Studio (бесплатно: https://ai.google.dev)
GEMINI_API_KEY=

# ── ИИ Модель ────────────────────────────────────────────────────────
GEMINI_MODEL=gemini-1.5-flash

# ── Настройки поиска на hh.ru ────────────────────────────────────────
HH_SEARCH_QUERY=Python developer
HH_AREA=113

# ── Фильтры ──────────────────────────────────────────────────────────
MIN_FIT_SCORE=7
MAX_APPLIES_PER_RUN=10
HEADLESS=False
NIGHT_MODE=False
BLACKLIST_EMPLOYERS=
TARGET_GRADE=Middle, Middle+, Senior
EXCLUDE_GRADES=junior,lead,intern,стажер,младший,джун,tech lead,техлид

# ── Персонализация писем ─────────────────────────────────────────────
USER_CONTACTS=
USER_SPECIAL_WISHES=
"""

# ─── Шаблон resume.txt ───────────────────────────────────────────────
_RESUME_TEMPLATE = """\
=== ВСТАВЬТЕ СЮДА ВАШЕ РЕЗЮМЕ ===

Заполните этот файл своим резюме и сохраните.
Бот будет использовать его при генерации сопроводительных писем.

── Пример структуры ─────────────────────────────────────────────────

Опыт работы:
• Название компании (год — год): Описание роли и достижений

Ключевые навыки:
• Язык/технология 1
• Язык/технология 2

Образование:
• ВУЗ, специальность, год окончания

Контакты:
• Имя Фамилия
• Telegram: @username
"""


def setup_first_run(base_dir: Path) -> bool:
    """
    Создаёт необходимые файлы рядом с EXE при первом запуске.
    
    Args:
        base_dir: Папка рядом с EXE (или корень проекта в dev-режиме)
    
    Returns:
        True если это первый запуск (хотя бы один файл был создан)
    """
    is_first_run = False

    # ── .env (шаблон без реальных данных) ──
    env_path = base_dir / ".env"
    if not env_path.exists():
        try:
            env_path.write_text(_ENV_TEMPLATE, encoding="utf-8")
            is_first_run = True
            print(f"[FirstRun] Created .env template: {env_path}")
        except Exception as e:
            print(f"[FirstRun] ERROR creating .env: {e}")

    # ── resume.txt (шаблон) ──
    resume_path = base_dir / "resume.txt"
    if not resume_path.exists():
        try:
            resume_path.write_text(_RESUME_TEMPLATE, encoding="utf-8")
            is_first_run = True
            print(f"[FirstRun] Created resume.txt template: {resume_path}")
        except Exception as e:
            print(f"[FirstRun] ERROR creating resume.txt: {e}")

    # ── applied_jobs.txt (пустой лог откликов) ──
    applied_path = base_dir / "applied_jobs.txt"
    if not applied_path.exists():
        try:
            applied_path.write_text("", encoding="utf-8")
        except Exception:
            pass

    if is_first_run:
        print(f"[FirstRun] First launch detected. Files created in: {base_dir}")

    return is_first_run
