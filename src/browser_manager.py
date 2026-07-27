import os
import sys
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
    def run_auth_flow(cls):
        """
        Запускает браузер в видимом режиме для ручной авторизации пользователя на hh.ru.
        После успешного входа сохраняет состояние сессии в session.json.
        """
        print("\n=== Запуск ручной авторизации ===")
        print("1. Откроется окно браузера.")
        print("2. Войдите в свой аккаунт hh.ru удобным вам способом (SMS, почта, пароль).")
        print("3. Пройдите капчу, если потребуется.")
        print("4. После успешного входа вернитесь в консоль и нажмите Enter для завершения и сохранения сессии.")
        
        with sync_playwright() as p:
            # Запускаем браузер обязательно с графическим интерфейсом
            browser = cls._launch_browser(p, headless=False)
            
            # Создаем контекст с эмуляцией реального пользователя
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=cls.USER_AGENT
            )
            
            page = context.new_page()
            page.goto("https://hh.ru/login")
            
            input("\n👉 Войдите в аккаунт на hh.ru в открывшемся окне браузера.\nПосле того как вы увидите главную страницу hh.ru и убедитесь, что вошли, нажмите ENTER здесь...")
            
            # Сохраняем куки и состояние локального хранилища
            context.storage_state(path=str(Config.SESSION_FILE))
            print(f"[✅ Успешно] Сессия успешно сохранена в файл {Config.SESSION_FILE}")
            
            browser.close()

    @classmethod
    def get_context(cls, playwright: Playwright, headless: bool = False) -> tuple[Browser, BrowserContext]:
        """
        Запускает браузер и возвращает контекст с загруженной ранее сессией.
        """
        browser = cls._launch_browser(playwright, headless=headless)

        # Проверяем, существует ли файл сессии
        session_exists = Config.SESSION_FILE.exists()
        
        context_args = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": cls.USER_AGENT
        }
        
        if session_exists:
            print(f"[ℹ️] Загрузка сохраненной сессии из {Config.SESSION_FILE}...")
            context_args["storage_state"] = str(Config.SESSION_FILE)
        else:
            print("[⚠️ Предупреждение] Файл сессии не найден. Бот запустится без авторизации. Рекомендуется сначала запустить режим авторизации.")

        context = browser.new_context(**context_args)
        
        # Добавляем скрипт маскировки, чтобы уменьшить вероятность обнаружения ботов
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        return browser, context
