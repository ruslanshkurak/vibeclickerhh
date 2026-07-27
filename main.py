import sys
import os
from pathlib import Path

# Если мы в скомпилированном EXE, заставляем Playwright искать браузеры в глобальной папке пользователя
if getattr(sys, 'frozen', False):
    user_local = os.environ.get("LOCALAPPDATA")
    if user_local:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(user_local) / "ms-playwright")
    else:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / "AppData" / "Local" / "ms-playwright")
# Принудительно настраиваем вывод в кодировке UTF-8 для предотвращения UnicodeEncodeError на Windows
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
except AttributeError:
    pass  # Для старых версий Python, где нет reconfigure (хотя в 3.12 она есть)
import time
import random
import argparse
import re
from urllib.parse import quote, urlparse, parse_qs, urlencode, urlunparse
from playwright.sync_api import sync_playwright

try:
    import msvcrt
except ImportError:
    msvcrt = None

from src.config import Config
from src.browser_manager import BrowserManager
from src.gemini_service import GeminiService
from src.database import Database

GUI_MODE = False

def parse_args():
    parser = argparse.ArgumentParser(description="Автоотклик-бот для hh.ru с ИИ")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--auth", action="store_true", help="Запустить ручной вход для сохранения сессии")
    group.add_argument("--dry-run", action="store_true", help="Тестовый прогон (оценка и генерация писем БЕЗ отправки отклика)")
    group.add_argument("--run", action="store_true", help="Полноценный автоматический отклик")
    parser.add_argument("--gui-mode", action="store_true", help="Запущен из графического интерфейса GUI")
    return parser.parse_args()

def safe_input(prompt=""):
    global GUI_MODE
    if GUI_MODE:
        print(f"{prompt}", flush=True)
        try:
            line = sys.stdin.readline()
            return line.strip()
        except Exception:
            return ""
            
    if not sys.stdin or not sys.stdin.isatty():
        print(f"{prompt} [Авто-продолжение в GUI через 1 сек...]", flush=True)
        time.sleep(1.0)
        return ""
    try:
        return input(prompt)
    except EOFError:
        return ""

def play_system_sound(sound_type="error"):
    try:
        import winsound
        if sound_type == "error":
            winsound.MessageBeep(winsound.MB_ICONHAND)
        elif sound_type == "warning":
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        else:
            winsound.MessageBeep(winsound.MB_OK)
    except Exception:
        print("\a", end="", flush=True)

def check_pause():
    if Config.PAUSE_FILE.exists():
        print("[⏸️] Бот поставлен на паузу. Ожидание...", flush=True)
        while Config.PAUSE_FILE.exists():
            time.sleep(1.0)
        print("[▶️] Работа возобновлена.", flush=True)

def extract_job_id(url: str) -> str:
    """Извлекает числовой ID вакансии из URL."""
    parts = url.split("?")[0].split("/")
    for part in parts:
        if part.isdigit():
            return part
    return ""

def get_smart_dynamic_delay(apply_count: int) -> tuple[float, str]:
    """
    Генерирует интеллектуальную динамическую задержку с нелинейным распределением
    и регулярными естественными 'человеческими' перерывами.
    """
    # Каждые 3-5 откликов человек делает более длинный перерыв
    is_break = (apply_count > 0 and (apply_count % random.choice([3, 4, 5]) == 0))
    
    if is_break:
        delay = random.uniform(65.0, 120.0) + random.uniform(-4.0, 8.0)
        msg = f"[☕ Человеческий перерыв] Имитация чтения описания вакансии/пауза ({delay:.1f} сек)..."
    else:
        base_delay = random.triangular(22.0, 55.0, 32.0)
        jitter = random.uniform(-3.0, 5.0)
        delay = max(18.0, base_delay + jitter)
        msg = f"[⏳ Динамическое ожидание] Задержка между откликами ({delay:.1f} сек)..."
        
    return delay, msg

def process_bot(dry_run: bool = True):
    session_id = Database.start_session()
    start_time_stamp = time.time()
    try:
        return _process_bot(dry_run, session_id, start_time_stamp)
    finally:
        duration = int(time.time() - start_time_stamp)
        Database.end_session(session_id, duration)

def _process_bot(dry_run: bool = True, session_id: int = 0, start_time_stamp: float = 0.0):
    # Очистка оставшегося файла паузы от прошлых запусков
    if Config.PAUSE_FILE.exists():
        try:
            Config.PAUSE_FILE.unlink()
            print("[ℹ️] Очищен застрявший файл паузы от прошлого запуска.")
        except Exception:
            pass

    if not Config.DISABLE_AI:
        resume = Config.get_resume()
        if not resume:
            print("[❌ Ошибка] Файл resume.txt пуст или содержит шаблон. Пожалуйста, заполните резюме перед запуском бота!")
            return

    print("[ℹ️] Инициализация сервиса анализа...")
    ai_service = GeminiService()
    
    print("[ℹ️] Запуск браузера...")
    with sync_playwright() as p:
        browser, context = BrowserManager.get_context(p, headless=Config.HEADLESS)
        page = context.new_page()

        applied_count = 0
        skipped_count = 0
        error_count = 0
        current_page = Config.get_last_search_page() if Config.RESUME_FROM_LAST_PAGE else 0
        max_empty_pages = Config.MAX_EMPTY_PAGES
        empty_pages_in_a_row = 0
        consecutive_processed_skips = 0
        bot_start_time = time.time()
        max_work_seconds = (Config.WORK_TIME_HOURS * 3600) + (Config.WORK_TIME_MINUTES * 60)

        while applied_count < Config.MAX_APPLIES_PER_RUN:
            check_pause()
            
            if session_id and start_time_stamp:
                Database.update_session_duration(session_id, int(time.time() - start_time_stamp))
            
            # Проверяем лимит времени работы бота перед переходом на страницу
            if max_work_seconds > 0:
                elapsed = time.time() - bot_start_time
                if elapsed >= max_work_seconds:
                    print(f"\n[⏱️] Достигнут лимит времени работы бота ({Config.WORK_TIME_HOURS} ч. {Config.WORK_TIME_MINUTES} мин.). Автоматическая мягкая остановка работы.")
                    break
                
                remaining = max_work_seconds - elapsed
                elapsed_min = int(elapsed // 60)
                remaining_min = int(remaining // 60)
                print(f"[⏱️] Прошло времени: {elapsed_min} мин. Осталось работать: {remaining_min} / {int(max_work_seconds // 60)} мин.")

            # Сохраняем текущую страницу в .env, чтобы при прерывании продолжить с неё
            if Config.RESUME_FROM_LAST_PAGE:
                Config.save_last_page(current_page)

            # Формируем URL для поиска: поддерживаем как ключевые слова, так и готовые ссылки поиска с фильтрами
            query_raw = Config.HH_SEARCH_QUERY.strip()
            if query_raw.startswith("http://") or query_raw.startswith("https://") or "hh.ru/search" in query_raw:
                parsed_url = urlparse(query_raw)
                query_params = parse_qs(parsed_url.query)
                query_params['page'] = [str(current_page)]
                # Если в URL нет параметра area, но он задан в настройках — добавляем
                if 'area' not in query_params and Config.HH_AREA:
                    query_params['area'] = [Config.HH_AREA]
                new_query = urlencode(query_params, doseq=True)
                search_url = urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    parsed_url.fragment
                ))
            else:
                search_url = f"https://hh.ru/search/vacancy?text={quote(query_raw)}&area={Config.HH_AREA}&order_by=publication_time&page={current_page}"
            
            print(f"\n[🔎] Переход на страницу поиска {current_page + 1}: {search_url}")
            try:
                page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                # Ждем появления элементов в DOM
                page.wait_for_selector('[data-qa="vacancy-serp__vacancy"], a[data-qa="serp-item__title"], a[data-qa="vacancy-serp__vacancy-title"]', state="attached", timeout=10000)
            except Exception as e:
                # Проверяем, не пустая ли это страница результатов поиска (конец выдачи)
                has_header = page.locator('.supernova-header, [data-qa="search-input"], .header, .supernova-search-group').count() > 0
                has_vacancies = page.locator('a[data-qa="serp-item__title"], a[data-qa="vacancy-serp__vacancy-title"]').count() > 0
                
                is_empty_results = (
                    page.locator('[data-qa="vacancy-serp__empty"]').count() > 0 or
                    page.get_by_text("ничего не найдено", exact=False).count() > 0 or
                    page.get_by_text("Не найдено вакансий", exact=False).count() > 0 or
                    page.get_by_text("Похоже, по вашему запросу", exact=False).count() > 0 or
                    (has_header and not has_vacancies)
                )
                if is_empty_results:
                    print(f"[ℹ️] На странице {current_page + 1} вакансий не найдено (достигнут конец результатов поиска). Завершаем работу.")
                    if Config.RESUME_FROM_LAST_PAGE:
                        Config.save_last_page(0)
                    break

                # Если произошел таймаут, проверим, может элементы все же есть
                if page.locator('a[data-qa="serp-item__title"], a[data-qa="vacancy-serp__vacancy-title"]').count() > 0:
                    print("[ℹ️] Элементы найдены в DOM, игнорируем ошибку таймаута видимости.")
                else:
                    print(f"[⚠️] Не удалось загрузить вакансии на странице {current_page + 1}. Ошибка: {str(e).splitlines()[0][:100]}")
                    # Делаем скриншот для диагностики проблем
                    try:
                        import os
                        os.makedirs("logs", exist_ok=True)
                        screenshot_name = os.path.join("logs", f"search_error_page_{current_page + 1}.png")
                        page.screenshot(path=screenshot_name)
                        print(f"[ℹ️] Скриншот страницы сохранен в {screenshot_name}")
                    except Exception:
                        pass
                    
                    print(f"\n\a==============================================================")
                    print("🚨 СКРИПТ ПРИОСТАНОВЛЕН (ОШИБКА ПОИСКА)!")
                    print("Возможно, hh.ru требует пройти капчу или заблокировал доступ.")
                    print("==============================================================")
                    if Config.NIGHT_MODE:
                        print("[🌙 Ночной режим] Пропуск ошибки поиска. Завершаем работу.")
                        break
                    else:
                        play_system_sound("error")
                        user_input = safe_input("Нажмите ENTER для повторной попытки (или 'q' для выхода): ")
                        if user_input.strip().lower() == 'q':
                            break
                        continue # Повторяем попытку загрузить ту же страницу

            # Прокручиваем страницу вниз, чтобы подгрузить все элементы
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2.0)

            # Собираем ссылки на вакансии
            vacancy_links = page.locator('a[data-qa="serp-item__title"], a[data-qa="vacancy-serp__vacancy-title"]').all()
            if not vacancy_links:
                vacancy_links = page.locator('a[href*="/vacancy/"]').all()

            job_urls = []
            for link in vacancy_links:
                href = link.get_attribute("href")
                if href and "/vacancy/" in href and "/search/" not in href and "/advanced" not in href:
                    title = link.text_content()
                    if title:
                        title_lower = title.lower()
                        # Динамический фильтр Go-стека: применяется только если в поисковом запросе ищется Go/Golang
                        query_lower = Config.HH_SEARCH_QUERY.lower()
                        is_go_query = "golang" in query_lower or re.search(r'\bgo\b', query_lower) or "go-" in query_lower
                        
                        if is_go_query:
                            has_go = "golang" in title_lower or re.search(r'\bgo\b', title_lower) or "go-" in title_lower
                            other_techs = ["java", "python", "php", "c++", "c#", "ruby", "ios", "android", "frontend", "react", "angular", "vue", "1c", "1с", "qa", "тестировщик", "аналитик", "data scientist", "devops"]
                            has_other = any(tech in title_lower for tech in other_techs)
                            
                            if not has_go and has_other:
                                print(f"[⏭️ Скип] Вакансия '{title.strip()}' пропущена (не Go стек).")
                                continue

                        # Исключение неподходящих грейдов
                        has_excluded_grade = False
                        for grade in Config.EXCLUDE_GRADES:
                            if re.search(rf'\b{re.escape(grade)}\b', title_lower) or (len(grade) > 4 and grade in title_lower):
                                has_excluded_grade = True
                                break
                        
                        if has_excluded_grade and ("middle" in title_lower or "мидл" in title_lower):
                            has_excluded_grade = False
                                
                        if has_excluded_grade:
                            print(f"[⏭️ Скип] Вакансия '{title.strip()}' пропущена (неподходящий грейд).")
                            continue

                    clean_url = href.split("?")[0]
                    if clean_url not in job_urls:
                        job_urls.append(clean_url)

            if not job_urls:
                print(f"[ℹ️] На странице {current_page + 1} нет вакансий. Завершаем поиск.")
                if Config.RESUME_FROM_LAST_PAGE:
                    Config.save_last_page(0)
                break

            print(f"[📈] Найдено {len(job_urls)} уникальных вакансий на странице {current_page + 1}.")
            
            # Фильтруем вакансии, оставляя только новые
            unprocessed_jobs = []
            for job_url in job_urls:
                job_id = extract_job_id(job_url)
                if job_id:
                    if Config.is_already_applied(job_id):
                        consecutive_processed_skips += 1
                        if Config.MAX_CONSECUTIVE_PROCESSED_SKIPS > 0 and consecutive_processed_skips >= Config.MAX_CONSECUTIVE_PROCESSED_SKIPS:
                            print(f"\n[🏁] Достигнут предел в {Config.MAX_CONSECUTIVE_PROCESSED_SKIPS} ранее обработанных вакансий подряд. Бот перешел к старой истории. Автоматическая остановка работы.")
                            break
                    else:
                        consecutive_processed_skips = 0  # Сбрасываем счетчик при нахождении новой вакансии
                        unprocessed_jobs.append((job_id, job_url))

            # Если мы вышли по брейку из-за предела подряд обработанных вакансий, завершаем весь цикл
            if Config.MAX_CONSECUTIVE_PROCESSED_SKIPS > 0 and consecutive_processed_skips >= Config.MAX_CONSECUTIVE_PROCESSED_SKIPS:
                break

            if not unprocessed_jobs:
                print(f"[⏭️] Все вакансии на странице {current_page + 1} уже обрабатывались ранее. Переходим к следующей...")
                time.sleep(1.5)
                current_page += 1
                empty_pages_in_a_row += 1
                if max_empty_pages > 0 and empty_pages_in_a_row >= max_empty_pages:
                    print(f"[🏁] Пропущено {max_empty_pages} страниц подряд с уже обработанными вакансиями. Поиск завершен.")
                    break
                continue

            empty_pages_in_a_row = 0
            print(f"[⚙️] Найдено {len(unprocessed_jobs)} новых вакансий для обработки на странице {current_page + 1}.")

            for index, (job_id, job_url) in enumerate(unprocessed_jobs):
                if applied_count >= Config.MAX_APPLIES_PER_RUN:
                    print(f"[🎯] Достигнут лимит откликов за запуск ({Config.MAX_APPLIES_PER_RUN}). Завершение работы.")
                    break

                # Проверяем лимит времени работы бота перед обработкой вакансии (мягкая остановка)
                if max_work_seconds > 0 and (time.time() - bot_start_time) >= max_work_seconds:
                    print(f"\n[⏱️] Достигнут лимит времени работы бота ({Config.WORK_TIME_HOURS} ч. {Config.WORK_TIME_MINUTES} мин.). Автоматическая мягкая остановка работы.")
                    break

                print(f"\n🚀 [{applied_count + 1}/{Config.MAX_APPLIES_PER_RUN}] Обработка вакансии {job_id} на стр. {current_page + 1}: {job_url}")
                
                # Задаем дефолтные значения перед try, чтобы избежать NameError при ошибках
                vacancy_title = "Неизвестно"
                company_name = "Неизвестно"
                score = 0
                reason = "Не оценено"
                cover_letter = ""

                try:
                    # Переходим на страницу вакансии
                    page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(random.uniform(2.0, 4.0)) # Имитация чтения человеком

                    # Парсим название компании и проверяем черный список
                    title_element = page.locator('[data-qa="vacancy-title"], h1').first
                    vacancy_title = title_element.inner_text().strip() if title_element.count() else "Неизвестно"
                    
                    company_element = page.locator('[data-qa="vacancy-company-name"]').first
                    if company_element.count():
                        company_name = company_element.inner_text().strip()
                    
                    if company_name and Config.is_employer_blacklisted(company_name):
                        print(f"[🚫 Блэклист] Компания '{company_name}' находится в черном списке. Пропускаем.")
                        Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, status="Пропущено (Черный список)")
                        skipped_count += 1
                        continue

                    # Проверяем, нет ли признаков того, что мы уже откликались ранее
                    already_applied = False
                    try:
                        # Сначала определяем общий контейнер вакансии
                        main_container = None
                        for selector in ['[data-qa="vacancy-view"]', '.vacancy-section', '#content']:
                            loc = page.locator(selector)
                            if loc.count() > 0:
                                main_container = loc.first
                                break

                        # Ищем шапку или верхнюю часть вакансии, где выводится статус отклика
                        header_container = None
                        for selector in ['[data-qa="vacancy-header"]', '.vacancy-header']:
                            loc = page.locator(selector)
                            if loc.count() > 0:
                                header_container = loc.first
                                break
                        
                        # Если шапку не нашли, в качестве контейнера для поиска статуса используем main_container
                        status_container = header_container if header_container else main_container
                        
                        if status_container:
                            if status_container.get_by_text("Вы откликнулись", exact=False).count() > 0 or \
                               status_container.get_by_text("Вы уже откликались", exact=False).count() > 0 or \
                               status_container.locator('a:has-text("Посмотреть отклик")').count() > 0 or \
                               status_container.locator('button:has-text("Посмотреть отклик")').count() > 0 or \
                               status_container.locator('[data-qa="vacancy-response-link-view"]').count() > 0:
                                already_applied = True
                        
                        # Глобальный фолбек по уникальному селектору кнопки просмотра отклика
                        if not already_applied:
                            if page.locator('[data-qa="vacancy-response-link-view"]').count() > 0:
                                already_applied = True
                    except Exception:
                        pass

                    if already_applied:
                        print(f"[ℹ️] Вы уже откликались на вакансию '{vacancy_title}' (компания '{company_name}'). Помечаем как обработанную.")
                        Config.log_applied(job_id)
                        Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=0, ai_reason="Уже откликался ранее", status="Уже откликался")
                        skipped_count += 1
                        continue

                    # Парсим текст вакансии
                    description_element = page.locator('[data-qa="vacancy-description"]').first
                    if not description_element.count():
                        description_element = page.locator('.g-user-content').first

                    if not description_element.count():
                        print("[⚠️] Не удалось извлечь описание вакансии. Пропускаем.")
                        error_count += 1
                        continue

                    vacancy_text = description_element.inner_text()
                    
                    # Оценка соответствия (если не отключено)
                    if Config.DISABLE_AI:
                        print("[ℹ️] Авто-оценка отключена в настройках. Автоматическое одобрение.")
                        score = 10
                        reason = "Авто-оценка отключена"
                    else:
                        print("[📊] Анализ соответствия вакансии...")
                        evaluation = ai_service.evaluate_vacancy(resume, vacancy_text)
                        score = evaluation["score"]
                        reason = evaluation["reason"]

                    print(f"[📈 Оценка соответствия]: {score}/10")
                    print(f"[💬 Вывод анализа]: {reason}")

                    if score < Config.MIN_FIT_SCORE:
                        print(f"[⏭️] Оценка {score} ниже минимального порога {Config.MIN_FIT_SCORE}. Пропускаем вакансию.")
                        Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, status="Пропущено (Низкая оценка ИИ)")
                        skipped_count += 1
                        continue

                    # Генерируем или подставляем сопроводительное письмо
                    if Config.USE_TEMPLATE_LETTER or Config.DISABLE_AI:
                        print("[📝] Использование шаблонного сопроводительного письма...")
                        cover_letter = Config.TEMPLATE_LETTER_TEXT if Config.TEMPLATE_LETTER_TEXT else "Здравствуйте! Меня заинтересовала ваша вакансия. Буду рад обсудить подробности на собеседовании."
                    else:
                        print("[📝] Составление сопроводительного письма под вакансию...")
                        cover_letter = ai_service.generate_cover_letter(resume, vacancy_text)
                    print(f"--- Сопроводительное письмо ---\n{cover_letter}\n-----------------------------")

                    # Ищем кнопку отклика.
                    apply_button = None
                    
                    check_pause()

                    # Принудительно скроллим вверх, чтобы Playwright не находил кнопки из футера/похожих вакансий
                    try:
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(0.5)
                    except Exception:
                        pass
                        
                    # 1. Сначала ищем основной data-qa селектор (уникален для главной вакансии)
                    top_button_locator = page.locator('[data-qa="vacancy-response-link-top"], [data-qa="vacancy-response-link-view"]')
                    for i in range(top_button_locator.count()):
                        candidate = top_button_locator.nth(i)
                        if candidate.is_visible():
                            apply_button = candidate
                            break
                    if not apply_button and top_button_locator.count() > 0:
                        apply_button = top_button_locator.first
                        
                    # 2. Если по уникальному селектору не нашли, ищем по тексту "Откликнуться"
                    # ТОЛЬКО внутри основного контейнера вакансии или заголовка. 
                    text_selectors = [
                        'a:has-text("Откликнуться")',
                        'button:has-text("Откликнуться")',
                        'span:has-text("Откликнуться")'
                    ]
                    
                    if not apply_button:
                        # Ищем контейнеры шапки или тела вакансии, исключая футер с рекомендациями
                        containers = [
                            page.locator('[data-qa="vacancy-header"], .vacancy-header'),
                            page.locator('[data-qa="vacancy-view"], .vacancy-section')
                        ]
                        for container in containers:
                            if container.count() > 0:
                                for selector in text_selectors:
                                    loc = container.first.locator(selector)
                                    for i in range(loc.count()):
                                        candidate = loc.nth(i)
                                        if candidate.is_visible():
                                            apply_button = candidate
                                            break
                                    if apply_button:
                                        break
                            if apply_button:
                                break

                    if not apply_button or not apply_button.count():
                        print("[⚠️] Кнопка отклика не найдена. Возможно, вы уже откликались, вакансия закрыта или это нестандартная страница.")
                        Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Пропущено (Кнопка не найдена)")
                        error_count += 1
                        continue

                    if dry_run:
                        print("[🧪 ТЕСТОВЫЙ РЕЖИМ] Отклик НЕ отправлен. Переходим к следующей вакансии.")
                        Config.log_applied(job_id)
                        Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Успешно (Тестовый режим)")
                        applied_count += 1
                        continue

                    # Кликаем "Откликнуться"
                    print("[🖱️] Клик по кнопке 'Откликнуться'...")
                    apply_button.click()
                    time.sleep(random.uniform(2.0, 3.5))
                    
                    check_pause()

                    # Если перекинуло на страницу анкеты (иногда hh так делает)
                    if "vacancy_response" in page.url or "test" in page.url:
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=5000)
                            time.sleep(2.0)
                        except Exception:
                            pass
                    
                    # Скроллим вверх страницы, чтобы увидеть блок с сопроводительным письмом
                    try:
                        page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(1.0)
                    except Exception:
                        pass
                            
                    # Проверяем, открыто ли поле для сопроводительного письма
                    letter_input = page.locator('[data-qa="vacancy-response-letter-input"], textarea[name="text"], [data-qa="vacancy-response-popup-form-letter-input"]').first
                    
                    # Если поле не видно, пробуем найти и нажать ссылку/кнопку "Приложить сопроводительное письмо"
                    if not (letter_input.count() and letter_input.is_visible()):
                        # Стратегия 1: ищем по data-qa атрибуту
                        letter_toggle = page.locator('[data-qa="vacancy-response-letter-toggle"]')
                        
                        # Стратегия 2: ищем по тексту ссылки
                        if not (letter_toggle.count() and letter_toggle.is_visible()):
                            letter_toggle = page.get_by_text("Приложить сопроводительное письмо", exact=False)
                        
                        # Стратегия 3: ищем кнопку с текстом "сопроводительное"
                        if not (letter_toggle.count() and letter_toggle.is_visible()):
                            letter_toggle = page.locator('button:has-text("сопроводительное"), a:has-text("сопроводительное")')
                        
                        if letter_toggle.count() and letter_toggle.is_visible():
                            print("[📝] Найдена ссылка 'Приложить сопроводительное письмо'. Кликаем...")
                            try:
                                letter_toggle.first.scroll_into_view_if_needed()
                                time.sleep(0.5)
                                letter_toggle.first.click(timeout=3000)
                                time.sleep(2.0)
                                # Перевычисляем локатор поля после открытия
                                letter_input = page.locator('[data-qa="vacancy-response-letter-input"], textarea[name="text"], [data-qa="vacancy-response-popup-form-letter-input"], textarea').first
                            except Exception as e:
                                print(f"[⚠️] Не удалось кликнуть по ссылке сопроводительного письма: {e}")
                        else:
                            print("[⚠️] Ссылка 'Приложить сопроводительное письмо' не найдена на странице.")

                    # Заполняем поле ввода сопроводительного письма
                    letter_filled = False
                    if letter_input.count() and letter_input.is_visible():
                        print("[✍️] Ввод сопроводительного письма...")
                        try:
                            # Кликнем и сфокусируемся
                            letter_input.click()
                            time.sleep(random.uniform(0.5, 1.0))
                            
                            # Очищаем поле (выделяем всё и удаляем)
                            letter_input.press("Control+a")
                            time.sleep(0.2)
                            letter_input.press("Backspace")
                            time.sleep(0.3)
                            
                            # Вставляем текст письма
                            letter_input.fill(cover_letter)
                            time.sleep(random.uniform(1.0, 2.0))
                            
                            # Эмулируем небольшое ручное редактирование (добавим пробел и сотрем его)
                            letter_input.press("Space")
                            time.sleep(0.2)
                            letter_input.press("Backspace")
                            time.sleep(random.uniform(1.5, 3.0))
                            
                            try:
                                actual_val = letter_input.input_value()
                                if len(actual_val) > 10:
                                    letter_filled = True
                                    print("[✔️] Письмо успешно заполнено.")
                            except Exception:
                                pass
                        except Exception as e:
                            print(f"[⚠️] Не удалось заполнить поле ввода: {e}")

                    # Ищем финальную кнопку отправки отклика (в попапе или на странице)
                    submit_button = page.locator('[data-qa="vacancy-response-submit-popup"], [data-qa="vacancy-response-submit-inline"], [data-qa="vacancy-response-submit-bottom"], button:has-text("Отправить"), button:has-text("Откликнуться с сопроводительным")').first
                    
                    # Даем до 2 секунд на появление кнопки
                    try:
                        submit_button.wait_for(state="visible", timeout=2000)
                    except Exception:
                        pass
                        
                    has_submit = submit_button.count() and submit_button.is_visible()
                    
                    if not letter_input.count() or not letter_input.is_visible():
                        if has_submit:
                            print("[⚠️] Поле для сопроводительного письма не найдено на экране.")

                    if has_submit:
                        if not letter_filled:
                            print("[❌ Ошибка] Сопроводительное письмо НЕ вставилось. Отменяем отклик.")
                            error_count += 1
                            # --- СОХРАНЯЕМ ДАМП HTML ДЛЯ ОТЛАДКИ ---
                            try:
                                import os
                                os.makedirs("logs", exist_ok=True)
                                with open(os.path.join("logs", "error_dump.html"), "w", encoding="utf-8") as f:
                                    f.write(page.content())
                                page.screenshot(path=os.path.join("logs", "error_screen.png"))
                                print("[🛠️] HTML-код сохранен в logs/error_dump.html для отладки!")
                            except Exception:
                                pass
                            # ---------------------------------------
                            close_btn = page.locator('[data-qa="vacancy-response-popup-close-button"], [data-qa="bot-close"]').first
                            if close_btn.count() and close_btn.is_visible():
                                close_btn.click()
                                
                            Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Требует ручной проверки")
                            continue

                        if Config.CONFIRM_APPLIES:
                            print(f"\n🚨 ТРЕБУЕТСЯ ПОДТВЕРЖДЕНИЕ ОТКЛИКА!")
                            print(f"Вакансия: {vacancy_title} ({company_name})")
                            print("Пожалуйста, проверьте вакансию и сопроводительное письмо в окне браузера.")
                            print("Нажмите 'Продолжить работу' в приложении (или ENTER в консоли) для отправки отклика.")
                            print("Для отмены/пропуска этой вакансии введите 'n' (или нажмите ENTER для отправки):")
                            play_system_sound("warning")
                            user_input = safe_input("Отправить отклик? (ENTER - Да, n - Пропустить/Продолжить дальше): ")
                            if user_input.strip().lower() == 'n':
                                print("[⏭️] Отклик пропущен по запросу пользователя.")
                                close_btn = page.locator('[data-qa="vacancy-response-popup-close-button"], [data-qa="bot-close"]').first
                                if close_btn.count() and close_btn.is_visible():
                                    close_btn.click()
                                Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Пропущено пользователем")
                                continue

                        print("[✔️] Нажатие кнопки подтверждения отправки...")
                        try:
                            submit_button.click(timeout=5000)
                            time.sleep(2.0)
                        except Exception:
                            print("[⚠️] Кнопка отправки заблокирована (требуется пройти тест). Пропускаем.")
                            Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Пропущено (Требуется тест)")
                            error_count += 1
                            continue
                            
                        # Проверяем успешность после отправки
                        try:
                            success_loc = page.get_by_text("Вы откликнулись").or_(
                                page.get_by_text("Отклик отправлен")
                            ).or_(
                                page.get_by_text("Резюме доставлено")
                            ).or_(
                                page.locator('[data-qa="vacancy-response-success-toast"]')
                            ).first
                            success_loc.wait_for(state="visible", timeout=2000)
                            print("[✔️] Отправка успешно завершена.")
                        except Exception:
                            current_url = page.url
                            if "vacancy_response" in current_url or "test" in current_url or len(context.pages) > 1:
                                print("[⚠️] Открылась анкета, тест или внешняя страница.")
                                print("[❌ Ошибка] Отменяем отклик.")
                                for p in context.pages[1:]:
                                    p.close()
                                Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Пропущено (Анкета/Тест)")
                                error_count += 1
                                continue
                            else:
                                print("[✔️] Отклик отправлен (без видимых предупреждений).")
                    else:
                        # Проверяем прямой отклик
                        try:
                            success_loc = page.get_by_text("Вы откликнулись").or_(
                                page.get_by_text("Отклик отправлен")
                            ).or_(
                                page.get_by_text("Резюме доставлено")
                            ).or_(
                                page.locator('[data-qa="vacancy-response-success-toast"]')
                            ).first
                            success_loc.wait_for(state="visible", timeout=3000)
                            print("[✔️] Отклик отправлен напрямую (без модального окна).")
                        except Exception:
                            current_url = page.url
                            if "vacancy_response" in current_url or "test" in current_url or len(context.pages) > 1:
                                print("[⚠️] Открылась анкета, тест или внешняя страница.")
                                print("[❌ Ошибка] Отменяем отклик.")
                                for p in context.pages[1:]:
                                    p.close()
                                Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Пропущено (Анкета/Тест)")
                                error_count += 1
                                continue
                            else:
                                print("[⚠️] Нестандартное окно или поведение после клика 'Откликнуться'.")
                                raise Exception("Отклик не подтвержден (возможно нестандартное окно)")

                    # Логируем успешный отклик
                    Config.log_applied(job_id)
                    Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Успешно отправлено")
                    applied_count += 1
                    print(f"[🎉 Успешно] Отправлен отклик на вакансию {job_id}!")



                    # Выжидаем большую паузу между реальными откликами
                    if session_id and start_time_stamp:
                        Database.update_session_duration(session_id, int(time.time() - start_time_stamp))
                    sleep_time = random.uniform(15.0, 30.0)
                    print(f"[⏳] Ожидание {sleep_time:.1f} сек... (нажмите 'p' для паузы)")
                    
                    end_time = time.time() + sleep_time
                    while time.time() < end_time:
                        try:
                            if msvcrt and msvcrt.kbhit():
                                key = msvcrt.getch()
                                if key.lower() == b'p':
                                    print("\n\a==============================================================")
                                    print("[⏸️] ПАУЗА (вызвана пользователем).")
                                    play_system_sound("warning")
                                    safe_input("Решите свои задачи и нажмите ENTER для продолжения работы...")
                                    print("==============================================================\n")
                                    while msvcrt.kbhit():
                                        msvcrt.getch()
                                    end_time = time.time() + (end_time - time.time())
                        except Exception:
                            pass
                        time.sleep(0.1)

                except Exception as e:
                    error_count += 1
                    # --- СОХРАНЯЕМ ДАМП HTML И СКРИНШОТ ПРИ ЛЮБОЙ ОШИБКЕ ---
                    try:
                        import os
                        os.makedirs("logs", exist_ok=True)
                        with open(os.path.join("logs", "error_dump.html"), "w", encoding="utf-8") as f:
                            f.write(page.content())
                        page.screenshot(path=os.path.join("logs", "error_screen.png"))
                        print("[🛠️] [ОШИБКА] HTML-код и скриншот сохранены in logs/ для анализа.")
                    except Exception:
                        pass
                    # ------------------------------------------------------
                    print(f"\n\a==============================================================")
                    print(f"🚨 СКРИПТ ПРИОСТАНОВЛЕН (ОШИБКА ОТКЛИКА)!")
                    print(f"Вакансия: {job_url}")
                    print(f"Ошибка: {str(e).splitlines()[0][:100]}...")
                    print("==============================================================")
                    
                    if Config.NIGHT_MODE:
                        print("[🌙 Ночной режим] Пропускаем вакансию и помечаем её для ручной проверки.")
                        Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Требует ручной проверки")
                        continue
                    else:
                        play_system_sound("error")
                        user_input = safe_input("Нажмите ENTER для перехода к СЛЕДУЮЩЕЙ вакансии (или 'q' для выхода): ")
                        
                        # В любом случае помечаем вакансию как требующую проверки
                        Database.log_vacancy(job_id, title=vacancy_title, company=company_name, url=job_url, ai_score=score, ai_reason=reason, cover_letter=cover_letter, status="Требует ручной проверки")
                        
                        if user_input.strip().lower() == 'q':
                            print("[🛑] Досрочное завершение работы по команде пользователя.")
                            break
                        continue

            # Переходим на следующую страницу поиска
            current_page += 1

        print(f"\n=======================================================")
        print(f"[🏁] Работа завершена.")
        print(f"[📊] ИТОГИ СЕССИИ:")
        print(f"    - Сделано откликов: {applied_count}")
        print(f"    - Пропущено вакансий: {skipped_count}")
        print(f"    - Ошибок при отклике: {error_count}")
        print(f"=======================================================\n")
        browser.close()

    print("\n=======================================================")
    print("[📊] ИНТЕРАКТИВНАЯ АНАЛИТИКА ГОТОВА!")
    print("Чтобы посмотреть воронку откликов, прочитать сгенерированные письма")
    print("и отметить тех, кто пригласил на собеседование, запусти в терминале:")
    print("python dashboard_app.py")
    print("=======================================================\n")

def main():
    global GUI_MODE
    args = parse_args()
    
    if args.gui_mode:
        GUI_MODE = True
        


    if args.auth:
        BrowserManager.run_auth_flow()
    elif args.dry_run:
        print("[🔥 Запуск] Режим тестирования (Dry-Run)...")
        process_bot(dry_run=True)
    elif args.run:
        print("[🚀 Запуск] Боевой режим (Автоотклик)...")
        process_bot(dry_run=False)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[🛑] Программа остановлена пользователем.")
        sys.exit(0)
