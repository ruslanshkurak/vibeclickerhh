import os
import sys
import time
import json
import threading
from pathlib import Path
from playwright.sync_api import Playwright, Browser, BrowserContext, sync_playwright
from src.config import Config

# Если мы в скомпилированном EXE, заставляем Playwright искать браузеры в глобальной папке пользователя
if getattr(sys, 'frozen', False):
    user_local = os.environ.get("LOCALAPPDATA")
    if user_local:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(user_local) / "ms-playwright")
    else:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / "AppData" / "Local" / "ms-playwright")

class BrowserManager:
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    @classmethod
    def _launch_browser(cls, playwright: Playwright, headless: bool = False) -> Browser:
        """
        Вспомогательный метод для безопасного запуска браузера.
        Пробует запустить системный Chrome, затем Edge, и только потом стандартный Chromium.
        """
        launch_args = {
            "headless": headless,
            "args": ["--disable-blink-features=AutomationControlled"]
        }

        # 1. Попытка запустить системный Google Chrome
        try:
            return playwright.chromium.launch(channel="chrome", **launch_args)
        except Exception:
            pass

        # 2. Попытка запустить системный Microsoft Edge (есть на всех современных Windows)
        try:
            return playwright.chromium.launch(channel="msedge", **launch_args)
        except Exception:
            pass

        # 3. Дефолтный Chromium (требует playwright install)
        print("[ℹ️] Системный Chrome/Edge не найден. Запуск стандартного Chromium...")
        return playwright.chromium.launch(**launch_args)

    @classmethod
    def _setup_context_protection(cls, context: BrowserContext):
        """
        Блокирует рекламные/трекинговые домены и автоматически закрывает всплывающие рекламные вкладки
        (включая MTS RTB: sm.rtb.mts.ru, Yandex Ads, Mail.ru), чтобы они не открывались в цикле.
        """
        bad_domains = [
            "rtb.mts.ru", "sm.rtb.mts.ru", "ad.mail.ru", "top-fwz1.mail.ru",
            "tns-counter.ru", "doubleclick.net", "googlesyndication.com",
            "an.yandex.ru", "mc.yandex.ru", "adfox.ru"
        ]

        def handle_page(new_page):
            try:
                # Никогда не закрываем первую (главную) страницу контекста
                if context.pages and new_page == context.pages[0]:
                    return
                # Даём вкладке время загрузить URL (редиректы с about:blank)
                try:
                    new_page.wait_for_load_state("commit", timeout=1500)
                except Exception:
                    pass
                url = new_page.url.lower() if new_page else ""
                # Закрываем всё, что не является страницей hh.ru
                if not url or "hh.ru" not in url:
                    new_page.close()
            except Exception:
                pass

        try:
            context.on("page", handle_page)
        except Exception:
            pass

        # Точечная блокировка рекламных доменов (не перехватываем остальной трафик)
        def abort_route(route):
            try:
                route.abort()
            except Exception:
                pass

        try:
            for domain in bad_domains:
                context.route(f"**/*{domain}*", abort_route)
        except Exception:
            pass

    @classmethod
    def run_auth_flow(cls):
        """
        Запускает браузер в видимом режиме для ручной авторизации пользователя на hh.ru.
        После успешного входа динамически сохраняет состояние сессии в session.json.
        """
        print("\n=== Запуск ручной авторизации ===")
        print("1. Откроется окно браузера.")
        print("2. Войдите в свой аккаунт hh.ru удобным вам способом (SMS, почта, пароль).")
        print("3. Пройдите капчу, если потребуется.")
        print("4. После входа сессия сохраняется автоматически. Вы также можете нажать 'Продолжить' в GUI или Enter в консоли.\n")
        
        with sync_playwright() as p:
            browser = cls._launch_browser(p, headless=False)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=cls.USER_AGENT
            )
            # НЕ подключаем _setup_context_protection при авторизации:
            # пользователь может входить через OAuth (Google, VK и т.д.),
            # и защита закроет эти легитимные всплывающие окна.
            
            page = context.new_page()
            page.goto("https://hh.ru/login")
            
            stop_event = threading.Event()
            
            def listen_input():
                try:
                    sys.stdin.readline()
                except Exception:
                    pass
                stop_event.set()
                
            input_thread = threading.Thread(target=listen_input, daemon=True)
            input_thread.start()
            
            login_detected = False
            
            while not stop_event.is_set():
                time.sleep(1.0)
                
                try:
                    if not browser.is_connected() or not context.pages or page.is_closed():
                        print("[ℹ️] Окно браузера было закрыто пользователем.")
                        break
                except Exception:
                    break
                    
                # Проверяем успешность входа по URL без непрерывных обращений к storage_state
                try:
                    curr_url = page.url.lower() if page else ""
                    is_logged_in_url = ("hh.ru" in curr_url and "/login" not in curr_url and "/account/login" not in curr_url and ("applicant" in curr_url or "resume" in curr_url or "vacancy" in curr_url or "search" in curr_url))
                    
                    if is_logged_in_url and not login_detected:
                        cookies = context.cookies()
                        has_auth_cookie = any(c.get('name') in ('hhtoken', 'hhrole', '_xsrf', 'session') for c in cookies)
                        if has_auth_cookie:
                            context.storage_state(path=str(Config.SESSION_FILE))
                            login_detected = True
                            print(f"[✅ Успешно] Вход зафиксирован! Авторизация сохранена в файл {Config.SESSION_FILE}")
                except Exception:
                    pass
            
            # Финальное сохранение состояния
            try:
                if browser.is_connected() and context.pages and not page.is_closed():
                    context.storage_state(path=str(Config.SESSION_FILE))
            except Exception:
                pass
                
            print(f"[✅ Успешно] Сессия успешно сохранена в файл {Config.SESSION_FILE}")
            
            try:
                browser.close()
            except Exception:
                pass

    @classmethod
    def get_context(cls, playwright: Playwright, headless: bool = False) -> tuple[Browser, BrowserContext]:
        """
        Запускает браузер и возвращает контекст с загруженной ранее сессией.
        """
        browser = cls._launch_browser(playwright, headless=headless)

        # Проверяем, существует ли валидный файл сессии
        session_exists = False
        if Config.SESSION_FILE.exists():
            try:
                if Config.SESSION_FILE.stat().st_size > 10:
                    with open(Config.SESSION_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and ("cookies" in data or "origins" in data):
                            session_exists = True
            except Exception as e:
                print(f"[⚠️ Предупреждение] Ошибка при чтении файла сессии {Config.SESSION_FILE}: {e}")
                session_exists = False

        context_args = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": cls.USER_AGENT
        }
        
        if session_exists:
            print(f"[ℹ️] Загрузка сохраненной сессии из {Config.SESSION_FILE}...")
            context_args["storage_state"] = str(Config.SESSION_FILE)
        else:
            print("[⚠️ Предупреждение] Валидный файл сессии не найден. Бот запустится без авторизации. Рекомендуется сначала запустить режим авторизации.")

        context = browser.new_context(**context_args)
        cls._setup_context_protection(context)
        
        # Добавляем скрипт маскировки, чтобы уменьшить вероятность обнаружения ботов
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        return browser, context

