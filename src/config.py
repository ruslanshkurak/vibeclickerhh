import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Определяем рабочую директорию:
# - В режиме EXE (frozen): папка рядом с .exe файлом
# - В режиме скрипта: корень проекта
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=True)

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    
    USE_TEMPLATE_LETTER = os.getenv("USE_TEMPLATE_LETTER", "False").lower() in ("true", "1", "yes")
    TEMPLATE_LETTER_TEXT = os.getenv("TEMPLATE_LETTER_TEXT", "").replace("\\n", "\n")
    DISABLE_AI = os.getenv("DISABLE_AI", "False").lower() in ("true", "1", "yes")
    CONFIRM_APPLIES = os.getenv("CONFIRM_APPLIES", "False").lower() in ("true", "1", "yes")
    
    HH_SEARCH_QUERY = os.getenv("HH_SEARCH_QUERY", "Python developer")
    HH_AREA = os.getenv("HH_AREA", "113")
    NIGHT_MODE = os.getenv("NIGHT_MODE", "False").lower() in ("true", "1", "yes")
    USER_CONTACTS = os.getenv("USER_CONTACTS", "").replace("\\n", "\n")
    USER_SPECIAL_WISHES = os.getenv("USER_SPECIAL_WISHES", "").replace("\\n", "\n")
    @staticmethod
    def _safe_int(val, default=0):
        if val is None:
            return default
        val = str(val).strip()
        if not val:
            return 0
        try:
            return int(val)
        except ValueError:
            return default

    MIN_FIT_SCORE = _safe_int(os.getenv("MIN_FIT_SCORE"), 7)
    MAX_APPLIES_PER_RUN = _safe_int(os.getenv("MAX_APPLIES_PER_RUN"), 10)
    HEADLESS = os.getenv("HEADLESS", "False").lower() in ("true", "1", "yes")
    MAX_EMPTY_PAGES = _safe_int(os.getenv("MAX_EMPTY_PAGES"), 3)
    MAX_CONSECUTIVE_PROCESSED_SKIPS = _safe_int(os.getenv("MAX_CONSECUTIVE_PROCESSED_SKIPS"), 10)
    LAST_SEARCH_PAGE = _safe_int(os.getenv("LAST_SEARCH_PAGE"), 0)
    RESUME_FROM_LAST_PAGE = os.getenv("RESUME_FROM_LAST_PAGE", "True").lower() in ("true", "1", "yes")
    WORK_TIME_HOURS = _safe_int(os.getenv("WORK_TIME_HOURS"), 0)
    WORK_TIME_MINUTES = _safe_int(os.getenv("WORK_TIME_MINUTES"), 0)

    # Считываем черный список компаний
    BLACKLIST_EMPLOYERS = [x.strip().lower() for x in os.getenv("BLACKLIST_EMPLOYERS", "").split(",") if x.strip()]
    
    # Настройки грейда
    TARGET_GRADE = os.getenv("TARGET_GRADE", "Middle, Middle+, Senior")
    EXCLUDE_GRADES = [x.strip().lower() for x in os.getenv("EXCLUDE_GRADES", "junior,lead,intern,стажер,младший,джун,tech lead,техлид").split(",") if x.strip()]
    
    SESSION_FILE = BASE_DIR / "session.json"
    RESUME_FILE = BASE_DIR / "resume.txt"
    APPLIED_LOG_FILE = BASE_DIR / "applied_jobs.txt"
    PAUSE_FILE = BASE_DIR / "pause.flag"


    @classmethod
    def save_last_page(cls, page: int):
        """Сохраняет текущую страницу поиска в БД."""
        cls.LAST_SEARCH_PAGE = page
        try:
            from src.database import Database
            Database.set_state("LAST_SEARCH_PAGE", str(page))
        except Exception as e:
            print(f"Ошибка сохранения LAST_SEARCH_PAGE: {e}")

    @classmethod
    def get_last_search_page(cls) -> int:
        """Получает текущую страницу поиска из БД или .env."""
        try:
            from src.database import Database
            val = Database.get_state("LAST_SEARCH_PAGE")
            if val != "":
                return cls._safe_int(val, 0)
        except Exception:
            pass
        return cls.LAST_SEARCH_PAGE

    @classmethod
    def is_employer_blacklisted(cls, employer_name: str) -> bool:
        """Проверяет, находится ли работодатель в черном списке."""
        if not employer_name:
            return False
        name_lower = employer_name.lower()
        for blacklisted in cls.BLACKLIST_EMPLOYERS:
            if blacklisted in name_lower:
                return True
        return False

    @classmethod
    def get_resume(cls) -> str:
        """Читает текст резюме из файла. Если файла нет, создает его из шаблона."""
        if not cls.RESUME_FILE.exists():
            example_path = cls.RESUME_FILE.with_name("resume.txt.example")
            if example_path.exists():
                try:
                    import shutil
                    shutil.copy(example_path, cls.RESUME_FILE)
                    print("📄 Файл resume.txt не найден. Создан шаблон на основе resume.txt.example")
                except Exception as e:
                    print(f"Не удалось скопировать resume.txt.example: {e}")
                    return ""
            else:
                return ""
        try:
            with open(cls.RESUME_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                if "=== ВСТАВЬТЕ СЮДА ВАШЕ РЕЗЮМЕ" in content or "Иван Иванов" in content:
                    return "" # Еще не заполнили резюме (или там шаблон)
                return content.strip()
        except Exception as e:
            print(f"Ошибка при чтении резюме: {e}")
            return ""

    @classmethod
    def is_already_applied(cls, job_id: str) -> bool:
        """Проверяет, откликались ли мы уже на эту вакансию (через БД или лог-файл)."""
        try:
            from src.database import Database
            if Database.is_already_applied(job_id):
                return True
        except Exception:
            pass
            
        if cls.APPLIED_LOG_FILE.exists():
            try:
                with open(cls.APPLIED_LOG_FILE, "r", encoding="utf-8") as f:
                    return str(job_id) in f.read().splitlines()
            except Exception:
                pass
        return False

    @classmethod
    def log_applied(cls, job_id: str):
        """Логирует успешный отклик в резервный текстовый файл."""
        try:
            with open(cls.APPLIED_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{job_id}\n")
        except Exception as e:
            print(f"Не удалось записать лог для вакансии {job_id}: {e}")

