import os
import sys
import threading
import traceback
from pathlib import Path

# Настройка UTF-8 для корректного вывода в консоль/терминал на Windows
try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass

# Глобальный обработчик необработанных исключений для трансляции в терминал
_CURRENT_APP_INSTANCE = None

def _global_excepthook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    err_formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        sys.stderr.write(f"\n[❌ НЕОБРАБОТАННОЕ ИСКЛЮЧЕНИЕ]:\n{err_formatted}\n")
        sys.stderr.flush()
    except Exception:
        pass
    if _CURRENT_APP_INSTANCE and hasattr(_CURRENT_APP_INSTANCE, "write_log"):
        try:
            _CURRENT_APP_INSTANCE.write_log(f"\n[❌ Сбой приложения]: {exc_value}\n{err_formatted}\n", tag="error")
        except Exception:
            pass

sys.excepthook = _global_excepthook
if hasattr(threading, 'excepthook'):
    threading.excepthook = lambda args: _global_excepthook(args.exc_type, args.exc_value, args.exc_traceback)

# Если мы в скомпилированном EXE, заставляем Playwright искать браузеры в глобальной папке пользователя
if getattr(sys, 'frozen', False):
    user_local = os.environ.get("LOCALAPPDATA")
    if user_local:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path(user_local) / "ms-playwright")
    else:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / "AppData" / "Local" / "ms-playwright")

import time
import subprocess
import re
from pathlib import Path
import customtkinter as ctk
import webbrowser
from dotenv import load_dotenv
# ── Рабочая директория: рядом с EXE (frozen) или корень проекта (скрипт) ──
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

def get_resource_path(relative_path: str) -> Path:
    """Получает абсолютный путь к ресурсу, учитывая PyInstaller frozen режим."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return BASE_DIR / relative_path

# ── Первый запуск: создаём шаблоны .env и resume.txt ДО импорта Config ──
# Config читает .env при импорте, поэтому файл должен существовать заранее
from src.first_run import setup_first_run as _setup_first_run
_IS_FIRST_RUN = _setup_first_run(BASE_DIR)

# ── Загружаем настройки (теперь .env точно существует) ──
from src.config import Config
from src.database import Database
from dashboard_app import app as dashboard_flask_app

# Устанавливаем тёмную тему по умолчанию
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Регулярное выражение для удаления ANSI-кодов (цвета терминала) из логов
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# ============================================================
# 🎨 ПРЕМИАЛЬНАЯ ЦВЕТОВАЯ ПАЛИТРА
# ============================================================
class Theme:
    # Основные фоны (ChatGPT / Gemini Dark)
    BG_DARKEST = "#09090b"    # Ультра-темный (Gemini)
    BG_DARK = "#0f0f11"       # Глубокий серый (ChatGPT/Gemini)
    BG_CARD = "#18181b"       # Чистый темный для карточек
    BG_CARD_HOVER = "#232329" # Интерактивный hover для карточек
    BG_ELEVATED = "#27272a"   # Элементы второго уровня

    # Акцентные цвета
    ACCENT_PRIMARY = "#6366f1"    # Indigo / Gemini Blue
    ACCENT_VIOLET = "#8b5cf6"     # Premium Purple
    ACCENT_CYAN = "#06b6d4"       # Modern Cyan
    ACCENT_GREEN = "#10b981"      # Emerald
    ACCENT_RED = "#f43f5e"        # Rose
    ACCENT_AMBER = "#f59e0b"      # Amber

    # Кнопки (в стиле ChatGPT / Gemini)
    BTN_GREEN = "#10a37f"         # Фирменный зеленый ChatGPT
    BTN_GREEN_HOVER = "#1a7f64"
    BTN_VIOLET = "#4f46e5"        # Indigo
    BTN_VIOLET_HOVER = "#4338ca"
    BTN_RED = "#ef4444"           # Red
    BTN_RED_HOVER = "#dc2626"
    BTN_CYAN = "#0ea5e9"          # Ocean Cyan
    BTN_CYAN_HOVER = "#0284c7"

    # Текст
    TEXT_PRIMARY = "#ececf1"      # Светлый контрастный текст (ChatGPT)
    TEXT_SECONDARY = "#c5c5d2"    # Мягкий вторичный
    TEXT_MUTED = "#71717a"        # Приглушенный
    TEXT_ACCENT = "#6366f1"       # Акцентный indigo

    # Разделители и границы
    BORDER = "#27272a"
    BORDER_ACCENT = "#3f3f46"
    SEPARATOR = "#27272a"

    # Статусы (индикаторы)
    STATUS_OFF = "#52525b"
    STATUS_ACTIVE = "#10b981"
    STATUS_WARNING = "#f59e0b"


APP_VERSION = "v1.0.2"
os.environ["APP_VERSION"] = APP_VERSION


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        global _CURRENT_APP_INSTANCE
        _CURRENT_APP_INSTANCE = self
        import tkinter as tk
        tk._default_root = self

        # Конфигурация главного окна
        self.title("VibeClickerHH.ru")
        self.geometry("1024x660")
        self.minsize(960, 580)
        self.configure(fg_color=Theme.BG_DARK)

        # Состояния фоновых процессов
        self.bot_process = None
        self.dashboard_process = None
        self.log_thread = None
        self.bot_running = False
        self.lic_badge = None  # Ссылка на бейдж лицензии в шапке (для обновления)
        
        # Перехват закрытия окна
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Установка иконки приложения
        icon_path = get_resource_path("image.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                try:
                    self.wm_iconbitmap(str(icon_path))
                except Exception:
                    pass

        # Создание основного контейнера
        self.grid_rowconfigure(1, weight=1)  # Контент
        self.grid_rowconfigure(2, weight=0)  # Футер
        self.grid_columnconfigure(0, weight=1)

        # ─── Брендированная шапка ───
        self.setup_header()

        # ─── Таб-панель (Вкладки) ───
        self.tabview = ctk.CTkTabview(
            self, 
            fg_color=Theme.BG_DARK,
            segmented_button_fg_color=Theme.BG_CARD, 
            segmented_button_selected_color=Theme.BTN_VIOLET,
            segmented_button_selected_hover_color=Theme.BTN_VIOLET_HOVER,
            segmented_button_unselected_hover_color=Theme.BG_ELEVATED,
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=12
        )
        self.tabview.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="nsew")

        # Создание вкладок
        self.tab_control = self.tabview.add("🎮  Панель управления")
        self.tab_settings = self.tabview.add("⚙️  Настройки бота")
        self.tab_resume = self.tabview.add("📝  Редактор резюме")

        # Инициализация интерфейсов вкладок
        self.setup_control_tab()
        self.setup_settings_tab()
        self.setup_resume_tab()

        # ─── Футер ───
        self.setup_footer()

        # Инициализация динамических карточек KPI
        self.bot_start_time = None
        self.current_applied_count = 0
        self.update_session_timer()

        # Автоматический запуск Flask дашборда в фоне при старте
        self.start_dashboard()



        # ─── Показываем приветствие при первом запуске ───
        if _IS_FIRST_RUN:
            self.after(800, self._show_first_run_dialog)

        # ─── Привязка горячих клавиш для русской раскладки клавиатуры ───
        self.bind_all("<Control-KeyPress>", self.setup_russian_hotkeys)
        self.bind("<Return>", lambda event: self.resume_bot() if hasattr(self, "btn_resume") and self.btn_resume.winfo_exists() and self.btn_resume.winfo_ismapped() else None)

        # Закрываем сплэш-скрин загрузки PyInstaller, если он запущен
        try:
            import pyi_splash
            pyi_splash.close()
        except ImportError:
            pass

    def setup_russian_hotkeys(self, event):
        # event.state & 4 проверяет, нажат ли Ctrl
        if event.state & 4:
            widget = event.widget
            if not widget:
                return
            
            key = event.keysym.lower()
            
            # Извлекаем реально сфокусированный виджет Tkinter
            try:
                focused = widget.focus_get()
            except Exception:
                focused = widget
                
            if not focused:
                return
                
            # Поддержка Ctrl+V (Вставить) - keysym 'м', keycode 86, char '\x16'
            if event.keycode == 86 or key == 'м' or event.char == '\x16':
                focused.event_generate("<<Paste>>")
                return "break"
            
            # Поддержка Ctrl+C (Копировать) - keysym 'с', keycode 67, char '\x03'
            elif event.keycode == 67 or key == 'с' or event.char == '\x03':
                focused.event_generate("<<Copy>>")
                return "break"
            
            # Поддержка Ctrl+X (Вырезать) - keysym 'ч', keycode 88, char '\x18'
            elif event.keycode == 88 or key == 'ч' or event.char == '\x18':
                focused.event_generate("<<Cut>>")
                return "break"
            
            # Поддержка Ctrl+A (Выделить всё) - keysym 'ф', keycode 65, char '\x01'
            elif event.keycode == 65 or key == 'ф' or event.char == '\x01':
                if hasattr(focused, "tag_add"):
                    focused.tag_add("sel", "1.0", "end")
                elif hasattr(focused, "select_range"):
                    focused.select_range(0, "end")
                    focused.icursor("end")
                else:
                    focused.event_generate("<<SelectAll>>")
                return "break"

    # ==========================================
    # 🏷️ Брендированная шапка
    # ==========================================
    def setup_header(self):
        header = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=0, height=56)
        header.grid(row=0, column=0, sticky="new", padx=0, pady=0)
        header.grid_columnconfigure(1, weight=1)
        header.grid_propagate(False)

        # Логотип + Название
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=20, pady=12, sticky="w")

        ctk.CTkLabel(
            brand_frame, text="🤖", 
            font=ctk.CTkFont(size=22)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            brand_frame, text="VibeClicker", 
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=Theme.ACCENT_PRIMARY
        ).pack(side="left")

        ctk.CTkLabel(
            brand_frame, text="HH.ru", 
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=Theme.ACCENT_VIOLET
        ).pack(side="left", padx=(4, 0))

        # Бейдж версии
        version_badge = ctk.CTkLabel(
            brand_frame, text=f"  {APP_VERSION}  ",
            font=ctk.CTkFont(size=9, weight="bold"),
            fg_color=Theme.BTN_VIOLET,
            corner_radius=6,
            text_color="#ffffff"
        )
        version_badge.pack(side="left", padx=(10, 0))

        # Правая часть: статус соединения
        status_conn = ctk.CTkFrame(header, fg_color="transparent")
        status_conn.grid(row=0, column=1, padx=20, pady=12, sticky="e")

        # Плашка лицензии (статичная для бесплатной версии)
        self.lic_badge = ctk.CTkLabel(
            status_conn, text="  🔑 Free Version  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Theme.BG_DARKEST,
            corner_radius=6,
            text_color=Theme.ACCENT_GREEN
        )
        self.lic_badge.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            status_conn, text="●",
            font=ctk.CTkFont(size=10),
            text_color=Theme.ACCENT_GREEN
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            status_conn, text="Система активна",
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")

        # Градиентная полоска-разделитель под шапкой
        accent_line = ctk.CTkFrame(self, fg_color=Theme.ACCENT_PRIMARY, height=2, corner_radius=0)
        accent_line.grid(row=0, column=0, sticky="sew", padx=0)

    # ==========================================
    # 🦶 Футер
    # ==========================================
    def setup_footer(self):
        footer = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=0, height=12)
        footer.grid(row=2, column=0, sticky="sew", padx=0, pady=0)
        footer.grid_columnconfigure(1, weight=1)
        footer.grid_propagate(False)

    def _show_first_run_dialog(self):
        """Приветственное окно при первом запуске — показывает что нужно настроить."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Добро пожаловать в VibeClickerHH.ru!")
        dialog.geometry("500x360")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.configure(fg_color=Theme.BG_CARD)
        dialog.grab_set()

        # Центрируем
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 250
        y = self.winfo_y() + (self.winfo_height() // 2) - 180
        dialog.geometry(f"+{x}+{y}")

        container = ctk.CTkFrame(
            dialog, fg_color=Theme.BG_CARD,
            corner_radius=16, border_width=1, border_color=Theme.ACCENT_PRIMARY
        )
        container.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(
            container, text="🚀  Первый запуск!",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.ACCENT_PRIMARY
        ).pack(pady=(24, 4))

        ctk.CTkLabel(
            container, text="Файлы конфигурации созданы рядом с программой.",
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_SECONDARY
        ).pack(pady=(0, 16))

        # Чеклист действий
        steps_frame = ctk.CTkFrame(container, fg_color=Theme.BG_DARKEST, corner_radius=10)
        steps_frame.pack(fill="x", padx=24, pady=(0, 16))

        steps = [
            ("1.", "Перейдите во вкладку «Настройки бота» и заполните API-ключ Gemini", Theme.ACCENT_AMBER),
            ("2.", "Вкладка «Редактор резюме» — вставьте ваше резюме", Theme.ACCENT_AMBER),
            ("3.", "Вкладка «Настройки бота» — настройте параметры поиска", Theme.ACCENT_CYAN),
            ("4.", "Запустите «Боевой автоотклик» и наблюдайте!", Theme.ACCENT_GREEN),
        ]
        for num, text, color in steps:
            row = ctk.CTkFrame(steps_frame, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(row, text=num, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color, width=20).pack(side="left")
            ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=11),
                         text_color=Theme.TEXT_SECONDARY).pack(side="left", padx=8)

        ctk.CTkButton(
            container, text="Понятно, начинаем! 🎉", width=220, height=40,
            fg_color=Theme.BTN_VIOLET, hover_color=Theme.BTN_VIOLET_HOVER,
            corner_radius=10, font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ffffff",
            command=dialog.destroy
        ).pack(pady=(0, 24))

    # ==========================================
    # 🎮 Вкладка "Панель управления"
    # ==========================================
    def setup_control_tab(self):
        self.tab_control.configure(fg_color=Theme.BG_DARK)
        self.tab_control.grid_rowconfigure(0, weight=1)
        self.tab_control.grid_columnconfigure(1, weight=1) # Консоль тянется

        # ─── Левый сайдбар управления ───
        sidebar = ctk.CTkScrollableFrame(
            self.tab_control, fg_color=Theme.BG_CARD, 
            corner_radius=16, width=310,
            border_width=1, border_color=Theme.BORDER
        )
        sidebar.grid(row=0, column=0, padx=(10, 16), pady=10, sticky="nsew")

        # ── Карточка статуса бота ──
        status_card = ctk.CTkFrame(
            sidebar, fg_color=Theme.BG_DARKEST, 
            corner_radius=12, border_width=1, border_color=Theme.BORDER
        )
        status_card.pack(fill="x", padx=12, pady=(4, 2))

        status_inner = ctk.CTkFrame(status_card, fg_color="transparent")
        status_inner.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(
            status_inner, text="СТАТУС БОТА",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=Theme.TEXT_MUTED
        ).pack(anchor="w")

        status_row = ctk.CTkFrame(status_inner, fg_color="transparent")
        status_row.pack(fill="x", pady=(2, 0))

        # Светящийся индикатор
        self.status_indicator = ctk.CTkLabel(
            status_row, text="⬤", 
            font=ctk.CTkFont(size=20),
            text_color=Theme.STATUS_OFF
        )
        self.status_indicator.pack(side="left", padx=(0, 8))

        self.status_text_label = ctk.CTkLabel(
            status_row, text="Остановлен", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.STATUS_OFF
        )
        self.status_text_label.pack(side="left")

        # ── Секция кнопок ──
        ctk.CTkLabel(
            sidebar, text="УПРАВЛЕНИЕ",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=Theme.TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(4, 2))

        # Главная кнопка: Запустить автоотклик
        self.btn_run = ctk.CTkButton(
            sidebar, text="🚀  Запустить автоотклик", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=Theme.BTN_GREEN, hover_color=Theme.BTN_GREEN_HOVER,
            height=36, corner_radius=9,
            text_color="#ffffff",
            command=self.start_bot_run
        )
        self.btn_run.pack(fill="x", padx=12, pady=(0, 4))

        # Контейнер для кнопок при активном боте (Пауза / Стоп)
        self.running_controls_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        
        self.btn_pause = ctk.CTkButton(
            self.running_controls_frame, text="⏸ Пауза", 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Theme.BTN_VIOLET, hover_color=Theme.BTN_VIOLET_HOVER,
            height=32, corner_radius=9,
            text_color="#ffffff",
            command=self.toggle_pause
        )
        self.btn_pause.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_stop = ctk.CTkButton(
            self.running_controls_frame, text="⏹ Стоп", 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Theme.BTN_RED, hover_color=Theme.BTN_RED_HOVER,
            height=32, corner_radius=9,
            text_color="#ffffff",
            command=self.stop_bot
        )
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=(3, 0))

        # Кнопка: Продолжить (приостановленный скрипт)
        self.btn_resume = ctk.CTkButton(
            sidebar, text="▶️  Продолжить работу", 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Theme.BTN_GREEN, hover_color=Theme.BTN_GREEN_HOVER,
            height=32, corner_radius=9,
            text_color="#ffffff",
            command=self.resume_bot
        )

        # Кнопка: Авторизация
        self.btn_auth = ctk.CTkButton(
            sidebar, text="🔑  Авторизоваться на hh.ru", 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Theme.BTN_CYAN, hover_color=Theme.BTN_CYAN_HOVER,
            height=32, corner_radius=9,
            text_color="#ffffff",
            command=self.start_auth
        )
        self.btn_auth.pack(fill="x", padx=12, pady=(0, 4))

        # ── Разделитель ──
        ctk.CTkFrame(sidebar, height=1, fg_color=Theme.SEPARATOR).pack(fill="x", padx=16, pady=3)

        # ── Лимиты запуска ──
        ctk.CTkLabel(
            sidebar, text="ЛИМИТЫ ЗАПУСКА",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=Theme.TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(2, 2))

        limit_applies_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        limit_applies_row.pack(fill="x", padx=16, pady=(1, 2))
        
        ctk.CTkLabel(
            limit_applies_row, text="Лимит откликов:   ", 
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")
        
        self.entry_main_max_applies = ctk.CTkEntry(
            limit_applies_row, width=60, height=24,
            fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER, corner_radius=5,
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_PRIMARY
        )
        self.entry_main_max_applies.pack(side="left")
        self.entry_main_max_applies.insert(0, str(Config.MAX_APPLIES_PER_RUN))

        limit_time_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        limit_time_row.pack(fill="x", padx=16, pady=(1, 2))
        
        ctk.CTkLabel(
            limit_time_row, text="Время работы:   ", 
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Theme.TEXT_SECONDARY
        ).pack(side="left")
        
        self.entry_main_work_hours = ctk.CTkEntry(
            limit_time_row, width=38, height=24,
            fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER, corner_radius=5,
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_PRIMARY
        )
        self.entry_main_work_hours.pack(side="left")
        self.entry_main_work_hours.insert(0, str(Config.WORK_TIME_HOURS))
        
        ctk.CTkLabel(
            limit_time_row, text=" ч. ", 
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_MUTED
        ).pack(side="left")
        
        self.entry_main_work_minutes = ctk.CTkEntry(
            limit_time_row, width=38, height=24,
            fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER, corner_radius=5,
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_PRIMARY
        )
        self.entry_main_work_minutes.pack(side="left")
        self.entry_main_work_minutes.insert(0, str(Config.WORK_TIME_MINUTES))
        
        ctk.CTkLabel(
            limit_time_row, text=" мин.", 
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_MUTED
        ).pack(side="left")

        # ── Разделитель ──
        ctk.CTkFrame(sidebar, height=1, fg_color=Theme.SEPARATOR).pack(fill="x", padx=16, pady=3)

        # ── Автономный режим ──
        ctk.CTkLabel(
            sidebar, text="РЕЖИМ РАБОТЫ",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=Theme.TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(2, 2))

        self.switch_night = ctk.CTkSwitch(
            sidebar, text="  Автономный режим\n  (пропускать ошибки)", 
            font=ctk.CTkFont(size=10),
            progress_color=Theme.ACCENT_PRIMARY,
            button_color=Theme.ACCENT_VIOLET,
            button_hover_color=Theme.BTN_VIOLET_HOVER,
            text_color=Theme.TEXT_SECONDARY,
            command=self.toggle_night_mode
        )
        self.switch_night.pack(anchor="w", padx=16, pady=(2, 3))
        if Config.NIGHT_MODE:
            self.switch_night.select()

        self.switch_confirm = ctk.CTkSwitch(
            sidebar, text="  Подтверждать отклики\n  (проверка писем вручную)", 
            font=ctk.CTkFont(size=10),
            progress_color=Theme.ACCENT_PRIMARY,
            button_color=Theme.ACCENT_VIOLET,
            button_hover_color=Theme.BTN_VIOLET_HOVER,
            text_color=Theme.TEXT_SECONDARY,
            command=self.toggle_confirm_mode
        )
        self.switch_confirm.pack(anchor="w", padx=16, pady=(2, 4))
        if Config.CONFIRM_APPLIES:
            self.switch_confirm.select()

        # ── Разделитель ──
        ctk.CTkFrame(sidebar, height=1, fg_color=Theme.SEPARATOR).pack(fill="x", padx=16, pady=3)

        # ── Кнопка Аналитика ──
        ctk.CTkLabel(
            sidebar, text="АНАЛИТИКА",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=Theme.TEXT_MUTED
        ).pack(anchor="w", padx=16, pady=(2, 2))

        self.btn_dashboard = ctk.CTkButton(
            sidebar, text="📊  Открыть дашборд", 
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=Theme.BTN_CYAN, hover_color=Theme.BTN_CYAN_HOVER,
            height=32, corner_radius=9,
            text_color="#ffffff",
            command=self.open_dashboard_url
        )
        self.btn_dashboard.pack(fill="x", padx=12, pady=(0, 6))
        # ─── Правая часть (Карточки KPI + Консоль логов) ───
        right_container = ctk.CTkFrame(self.tab_control, fg_color="transparent")
        right_container.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        right_container.grid_rowconfigure(1, weight=1)
        right_container.grid_columnconfigure(0, weight=1)

        # ── Карточки KPI аналитики ──
        stats_frame = ctk.CTkFrame(right_container, fg_color="transparent")
        stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def _make_stat_card(parent, title, value_attr, default_val, icon, accent_color, col, font_size=14):
            card = ctk.CTkFrame(parent, fg_color=Theme.BG_CARD, corner_radius=12, border_width=1, border_color=Theme.BORDER)
            card.grid(row=0, column=col, padx=3, sticky="ew")
            
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=6, pady=(6, 2))
            
            ctk.CTkLabel(top_row, text=icon, font=ctk.CTkFont(size=12)).pack(side="left")
            ctk.CTkLabel(top_row, text=title.upper(), font=ctk.CTkFont(size=9, weight="bold"), text_color=Theme.TEXT_MUTED).pack(side="left", padx=4)
            
            val_lbl = ctk.CTkLabel(card, text=default_val, font=ctk.CTkFont(size=font_size, weight="bold"), text_color=accent_color)
            val_lbl.pack(anchor="w", padx=10, pady=(0, 6))
            setattr(self, value_attr, val_lbl)

        _make_stat_card(stats_frame, "Отклики", "lbl_stat_applies", f"{Database.get_successful_applies_count()} / {Config.MAX_APPLIES_PER_RUN}", "🚀", Theme.ACCENT_GREEN, 0, font_size=14)
        _make_stat_card(stats_frame, "Время сессии", "lbl_stat_time", "00:00:00", "⏱", Theme.ACCENT_CYAN, 1, font_size=14)
        _make_stat_card(stats_frame, "Оценка", "lbl_stat_score", "— / 10", "🎯", Theme.ACCENT_VIOLET, 2, font_size=14)
        _make_stat_card(stats_frame, "Задержка", "lbl_stat_mode", "Авто (Смарт)", "☕", Theme.ACCENT_AMBER, 3, font_size=12)

        # ─── Консоль логов ───
        console_frame = ctk.CTkFrame(
            right_container, fg_color=Theme.BG_DARKEST, 
            corner_radius=16, border_width=1, border_color=Theme.BORDER
        )
        console_frame.grid(row=1, column=0, sticky="nsew")
        console_frame.grid_rowconfigure(1, weight=1)
        console_frame.grid_columnconfigure(0, weight=1)

        # Шапка консоли
        console_header = ctk.CTkFrame(console_frame, fg_color="transparent")
        console_header.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")

        # Имитация «окна терминала» — три точки
        dots_frame = ctk.CTkFrame(console_header, fg_color="transparent")
        dots_frame.pack(side="left")

        for color in ["#ef4444", "#eab308", "#22c55e"]:
            ctk.CTkLabel(
                dots_frame, text="●", 
                font=ctk.CTkFont(size=9),
                text_color=color
            ).pack(side="left", padx=2)
        
        ctk.CTkLabel(
            console_header, text="   LIVE CONSOLE", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=Theme.TEXT_MUTED
        ).pack(side="left")
        
        # Кнопка очистки логов
        ctk.CTkButton(
            console_header, text="✕ Очистить", width=90, height=22, 
            fg_color=Theme.BG_ELEVATED, hover_color=Theme.BORDER_ACCENT, 
            font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=8, text_color=Theme.TEXT_SECONDARY,
            command=self.clear_console
        ).pack(side="right")

        # Текстовое поле логов
        self.txt_log = ctk.CTkTextbox(
            console_frame, 
            font=ctk.CTkFont(family="Consolas", size=12), 
            fg_color=Theme.BG_DARKEST, 
            text_color=Theme.TEXT_SECONDARY,
            wrap="word", corner_radius=10
        )
        self.txt_log.grid(row=1, column=0, padx=14, pady=(4, 14), sticky="nsew")
        # Оставляем state="normal" для возможности копирования, но блокируем ручное редактирование логов
        self.txt_log._textbox.bind("<Key>", self.block_input)

        # Контекстное меню для копирования логов
        import tkinter as tk
        self.log_context_menu = tk.Menu(
            self.txt_log._textbox, tearoff=0,
            bg=Theme.BG_CARD, fg=Theme.TEXT_PRIMARY,
            activebackground=Theme.BTN_VIOLET, activeforeground="#ffffff",
            bd=1, relief="flat"
        )
        self.log_context_menu.add_command(label="Копировать выделенное", command=self.copy_selected_log)
        self.log_context_menu.add_command(label="Копировать все логи", command=self.copy_all_logs)
        self.txt_log._textbox.bind("<Button-3>", self.show_log_context_menu)

        # Настройка цветных тегов для консоли
        self.txt_log._textbox.tag_config("success", foreground=Theme.ACCENT_GREEN)
        self.txt_log._textbox.tag_config("warning", foreground=Theme.ACCENT_AMBER)
        self.txt_log._textbox.tag_config("error", foreground=Theme.ACCENT_RED)
        self.txt_log._textbox.tag_config("info", foreground=Theme.ACCENT_CYAN)
        self.txt_log._textbox.tag_config("bot_action", foreground=Theme.ACCENT_VIOLET)

        # Приветственное сообщение
        self.write_log("[ℹ️] VibeClickerHH.ru запущен успешно\n", "info")
        self.write_log("[ℹ️] Сервер аналитики дашборда инициализируется...\n", "info")

    # ==========================================
    # ⚙️ Вкладка "Настройки"
    # ==========================================
    def setup_settings_tab(self):
        self.tab_settings.configure(fg_color=Theme.BG_DARK)
        self.tab_settings.grid_rowconfigure(0, weight=1)
        self.tab_settings.grid_columnconfigure(0, weight=1)

        # Контейнер с прокруткой для настроек
        scroll_frame = ctk.CTkScrollableFrame(
            self.tab_settings, fg_color="transparent",
            scrollbar_button_color=Theme.BG_ELEVATED,
            scrollbar_button_hover_color=Theme.BORDER_ACCENT
        )
        scroll_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        scroll_frame.grid_columnconfigure((0, 1), weight=1)

        # --- БЛОК 1: КЛЮЧИ И ИИ-МОДЕЛИ ---
        ai_frame = self._create_settings_card(scroll_frame, "🔑  ИИ И МОДЕЛИ ИНТЕЛЛЕКТА", Theme.ACCENT_PRIMARY)
        ai_frame.grid(row=0, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
        ai_frame.columnconfigure(1, weight=1)

        self._create_field_label(ai_frame, "Gemini API Key:", row=1)
        self.entry_api_key = self._create_entry(ai_frame, "Вставьте ваш API ключ...", row=1)
        self.entry_api_key.insert(0, Config.GEMINI_API_KEY)

        # Ссылка для получения бесплатного ключа
        self._create_field_label(ai_frame, "Где взять ключ:", row=2)
        self.lbl_api_link = ctk.CTkLabel(
            ai_frame,
            text="Получить бесплатный API-ключ в Google AI Studio",
            font=ctk.CTkFont(size=11, underline=True),
            text_color=Theme.ACCENT_CYAN,
            cursor="hand2"
        )
        self.lbl_api_link.grid(row=2, column=1, padx=16, pady=4, sticky="w")
        self.lbl_api_link.bind("<Button-1>", lambda e: webbrowser.open("https://aistudio.google.com/"))

        self._create_field_label(ai_frame, "ИИ Модель:", row=3)
        self.combobox_model = ctk.CTkComboBox(
            ai_frame, values=["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash", "gemma-4-26b-a4b-it"], 
            fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER,
            button_color=Theme.BG_ELEVATED, button_hover_color=Theme.BORDER_ACCENT,
            dropdown_fg_color=Theme.BG_CARD, dropdown_hover_color=Theme.BG_ELEVATED,
            font=ctk.CTkFont(size=12)
        )
        self.combobox_model.grid(row=3, column=1, padx=16, pady=8, sticky="ew")
        self.combobox_model.set(Config.GEMINI_MODEL)

        # Галочка: Использовать ИИ для оценки вакансий
        self.switch_disable_ai = ctk.CTkSwitch(
            ai_frame, text="  Использовать ИИ для оценки вакансий", 
            font=ctk.CTkFont(size=12, weight="bold"),
            progress_color=Theme.ACCENT_PRIMARY,
            button_color=Theme.ACCENT_VIOLET,
            button_hover_color=Theme.BTN_VIOLET_HOVER,
            text_color=Theme.TEXT_SECONDARY,
            command=self.toggle_ai_settings_state
        )
        self.switch_disable_ai.grid(row=4, column=0, columnspan=2, padx=16, pady=(8, 12), sticky="w")
        if not Config.DISABLE_AI:
            self.switch_disable_ai.select()

        # --- БЛОК 2: НАСТРОЙКИ ПОИСКА HH.RU ---
        search_frame = self._create_settings_card(scroll_frame, "🔎  НАСТРОЙКИ ПОИСКА HH.RU", Theme.ACCENT_CYAN)
        search_frame.grid(row=1, column=0, padx=8, pady=8, sticky="nsew")
        search_frame.columnconfigure(1, weight=1)

        self._create_field_label(search_frame, "Ключевые слова:", row=1)
        self.entry_search_query = self._create_entry(search_frame, "", row=1)
        self.entry_search_query.insert(0, Config.HH_SEARCH_QUERY)

        # Подсказка к ключевым словам
        self._create_hint(
            search_frame, 
            "💡 Рекомендуется: Настроить поиск и фильтры на hh.ru (например, 'в названии вакансии'),\n"
            "скопировать готовую ссылку из адресной строки и вставить её сюда. Это сделает\n"
            "выборку максимально точной и релевантной!",
            row=2
        )

        # Выбор Региона поиска
        self._create_field_label(search_frame, "Регион поиска:", row=3)
        self.regions_map = {
            "Вся Россия (113)": "113",
            "Все страны (Без фильтра)": "",
            "Москва (1)": "1",
            "Санкт-Петербург (2)": "2",
            "Татарстан (16)": "16",
            "Новосибирск (4)": "4",
            "Екатеринбург (3)": "3",
            "Казахстан (40)": "40",
            "Беларусь (16)": "16",
            "Указать вручную (код ID)": "custom"
        }
        self.combobox_region = ctk.CTkComboBox(
            search_frame, values=list(self.regions_map.keys()), 
            fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER,
            button_color=Theme.BG_ELEVATED, button_hover_color=Theme.BORDER_ACCENT,
            dropdown_fg_color=Theme.BG_CARD, dropdown_hover_color=Theme.BG_ELEVATED,
            font=ctk.CTkFont(size=12),
            command=self.on_region_selected
        )
        self.combobox_region.grid(row=3, column=1, padx=16, pady=8, sticky="ew")

        # Поиск ключа
        current_region_name = "Указать вручную (код ID)"
        for name, code in self.regions_map.items():
            if code == Config.HH_AREA:
                current_region_name = name
                break
        self.combobox_region.set(current_region_name)

        self._create_field_label(search_frame, "Код региона (ID):", row=4)
        self.entry_region_id = self._create_entry(search_frame, "", row=4)
        self.entry_region_id.insert(0, Config.HH_AREA)
        
        # Подсказка к коду региона
        self._create_hint(search_frame, "💡 Чтобы узнать ID региона, выберите его в поиске на hh.ru и найдите в URL 'area=ID'", row=5)

        # Отключаем ручной ввод, если выбран готовый пресет
        if current_region_name != "Указать вручную (код ID)":
            self.entry_region_id.configure(state="disabled")

        # --- БЛОК 3: ФИЛЬТРЫ И ГРЕЙДЫ ---
        filters_frame = self._create_settings_card(scroll_frame, "🎯  ФИЛЬТРЫ И ОЦЕНКИ ИИ", Theme.ACCENT_AMBER)
        filters_frame.grid(row=1, column=1, padx=8, pady=8, sticky="nsew")
        filters_frame.columnconfigure(1, weight=1)

        # 1. Минимальный балл соответствия
        self._create_field_label(filters_frame, "Миним. балл ИИ (1-10):", row=1, pady=(8, 2))
        self.entry_fit_score = self._create_entry(filters_frame, "", row=1, pady=(8, 2))
        self.entry_fit_score.insert(0, str(Config.MIN_FIT_SCORE))
        self._create_hint(filters_frame, "💡 Минимальная оценка соответствия резюме по шкале от 1 до 10", row=2)

        # 2. Лимит откликов
        self._create_field_label(filters_frame, "Лимит откликов:", row=3, pady=(8, 2))
        self.entry_max_applies = self._create_entry(filters_frame, "", row=3, pady=(8, 2))
        self.entry_max_applies.insert(0, str(Config.MAX_APPLIES_PER_RUN))
        self._create_hint(filters_frame, "💡 Максимальное количество откликов за один запуск бота", row=4)

        # 3. Исключить грейды, слова
        self._create_field_label(filters_frame, "Исключить грейды, слова:", row=5, pady=(8, 2))
        self.entry_exclude_grades = self._create_entry(filters_frame, "", row=5, pady=(8, 2))
        self.entry_exclude_grades.insert(0, ",".join(Config.EXCLUDE_GRADES))
        self._create_hint(filters_frame, "💡 Через запятую: junior, стажер — вакансии с этими словами будут пропущены", row=6)

        # 4. Исключить компании из поиска
        self._create_field_label(filters_frame, "Исключить компании из поиска:", row=7, pady=(8, 2))
        self.entry_blacklist = self._create_entry(filters_frame, "", row=7, pady=(8, 2))
        self.entry_blacklist.insert(0, ",".join(Config.BLACKLIST_EMPLOYERS))
        self._create_hint(filters_frame, "💡 Через запятую названия компаний для автоматического пропуска", row=8)

        # 5. Предел пустых страниц
        self._create_field_label(filters_frame, "Предел пустых страниц:", row=9, pady=(8, 2))
        self.entry_max_empty_pages = self._create_entry(filters_frame, "", row=9, pady=(8, 2))
        self.entry_max_empty_pages.insert(0, str(Config.MAX_EMPTY_PAGES))
        self._create_hint(filters_frame, "💡 Лимит пропуска страниц, где все вакансии уже просмотрены", row=10)

        # 6. Предел повторных вакансий подряд
        self._create_field_label(filters_frame, "Предел повторов подряд:", row=11, pady=(8, 2))
        self.entry_max_skips = self._create_entry(filters_frame, "", row=11, pady=(8, 2))
        self.entry_max_skips.insert(0, str(Config.MAX_CONSECUTIVE_PROCESSED_SKIPS))
        self._create_hint(filters_frame, "💡 Остановка при N подряд пропущенных (бот дошел до старой истории)", row=12, pady=(0, 10))

        # 7. Продолжить с последней страницы
        self.switch_resume_page = ctk.CTkSwitch(
            filters_frame, text="  Продолжить с последней страницы", 
            font=ctk.CTkFont(size=12, weight="bold"),
            progress_color=Theme.ACCENT_PRIMARY,
            button_color=Theme.ACCENT_VIOLET,
            button_hover_color=Theme.BTN_VIOLET_HOVER,
            text_color=Theme.TEXT_SECONDARY
        )
        self.switch_resume_page.grid(row=13, column=0, columnspan=2, padx=16, pady=(8, 2), sticky="w")
        if Config.RESUME_FROM_LAST_PAGE:
            self.switch_resume_page.select()
        self._create_hint(filters_frame, "💡 Бот продолжит поиск со страницы, на которой остановился в прошлый раз", row=14, pady=(0, 10))

        # 8. Начать со страницы
        self._create_field_label(filters_frame, "Начать со страницы:", row=15, pady=(8, 2))
        self.entry_last_page = self._create_entry(filters_frame, "", row=15, pady=(8, 2))
        self.entry_last_page.insert(0, str(Config.LAST_SEARCH_PAGE + 1))
        self._create_hint(filters_frame, "💡 Номер страницы (1 — первая страница). Бот автоматически обновляет её при работе.", row=16, pady=(0, 10))

        # 9. Лимит времени работы
        self._create_field_label(filters_frame, "Лимит времени работы:", row=17, pady=(8, 2))
        time_frame = ctk.CTkFrame(filters_frame, fg_color="transparent")
        time_frame.grid(row=17, column=1, padx=16, pady=(8, 2), sticky="w")
        
        self.entry_work_hours = ctk.CTkEntry(
            time_frame, width=50, fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER, corner_radius=8,
            font=ctk.CTkFont(size=12), text_color=Theme.TEXT_PRIMARY
        )
        self.entry_work_hours.pack(side="left")
        self.entry_work_hours.insert(0, str(Config.WORK_TIME_HOURS))
        
        ctk.CTkLabel(time_frame, text=" ч.  ", text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=11)).pack(side="left")
        
        self.entry_work_minutes = ctk.CTkEntry(
            time_frame, width=50, fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER, corner_radius=8,
            font=ctk.CTkFont(size=12), text_color=Theme.TEXT_PRIMARY
        )
        self.entry_work_minutes.pack(side="left")
        self.entry_work_minutes.insert(0, str(Config.WORK_TIME_MINUTES))
        
        ctk.CTkLabel(time_frame, text=" мин.", text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=11)).pack(side="left")
        
        self._create_hint(filters_frame, "💡 Автоматическая остановка бота через указанное время. 0 ч. 0 мин. — без лимита.", row=18, pady=(0, 14))

        # --- БЛОК 4: ИИ-ПЕРСОНАЛИЗАЦИЯ СОПРОВОДИТЕЛЬНЫХ ПИСЕМ ---
        pers_frame = self._create_settings_card(scroll_frame, "✍️  ПЕРСОНАЛИЗАЦИЯ ИИ-ПИСЕМ", Theme.ACCENT_VIOLET)
        pers_frame.grid(row=2, column=0, columnspan=2, padx=8, pady=8, sticky="ew")
        pers_frame.columnconfigure(1, weight=1)

        self._create_field_label(pers_frame, "Контакты для подписи:\n(будут в конце каждого письма)", row=1)
        self.txt_contacts = ctk.CTkTextbox(
            pers_frame, fg_color=Theme.BG_DARKEST, 
            border_color=Theme.BORDER, border_width=1, 
            height=80, corner_radius=10,
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_PRIMARY
        )
        self.txt_contacts.grid(row=1, column=1, padx=16, pady=8, sticky="ew")
        self.txt_contacts.insert("1.0", Config.USER_CONTACTS)

        self._create_field_label(pers_frame, "Особые пожелания и приоритеты:\n(стоп-условия -> 0 баллов;\nжелаемые технологии/условия -> +баллы)", row=2)
        self.txt_special_wishes = ctk.CTkTextbox(
            pers_frame, fg_color=Theme.BG_DARKEST, 
            border_color=Theme.BORDER, border_width=1, 
            height=80, corner_radius=10,
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_PRIMARY
        )
        self.txt_special_wishes.grid(row=2, column=1, padx=16, pady=8, sticky="ew")
        self.txt_special_wishes.insert("1.0", Config.USER_SPECIAL_WISHES)

        # Галочка: Использовать собственный шаблон вместо ИИ
        self.switch_use_template = ctk.CTkSwitch(
            pers_frame, text="  Использовать собственный шаблон вместо ИИ", 
            font=ctk.CTkFont(size=12, weight="bold"),
            progress_color=Theme.ACCENT_PRIMARY,
            button_color=Theme.ACCENT_VIOLET,
            button_hover_color=Theme.BTN_VIOLET_HOVER,
            text_color=Theme.TEXT_SECONDARY,
            command=self.toggle_template_state
        )
        self.switch_use_template.grid(row=3, column=0, columnspan=2, padx=16, pady=(12, 4), sticky="w")
        if Config.USE_TEMPLATE_LETTER:
            self.switch_use_template.select()

        # Текст шаблона письма
        self._create_field_label(pers_frame, "Текст шаблона письма:\n(будет отправлен как есть)", row=4)
        self.txt_template_letter = ctk.CTkTextbox(
            pers_frame, fg_color=Theme.BG_DARKEST, 
            border_color=Theme.BORDER, border_width=1, 
            height=120, corner_radius=10,
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_PRIMARY
        )
        self.txt_template_letter.grid(row=4, column=1, padx=16, pady=8, sticky="ew")
        self.txt_template_letter.insert("1.0", Config.TEMPLATE_LETTER_TEXT)

        # Контейнер для кнопок управления внизу вкладки
        buttons_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        buttons_frame.grid(row=3, column=0, columnspan=2, padx=8, pady=(12, 20), sticky="ew")
        buttons_frame.columnconfigure(0, weight=1)

        # Кнопка: Очистить пропущенные из базы
        self.btn_reset_skipped = ctk.CTkButton(
            buttons_frame, text="🧹  Сбросить историю пропусков ИИ", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=Theme.BTN_CYAN, hover_color=Theme.BTN_CYAN_HOVER,
            height=48, corner_radius=12,
            text_color="#ffffff",
            command=self.reset_skipped_vacancies
        )
        self.btn_reset_skipped.grid(row=0, column=0, sticky="ew")

        # Привязываем динамическое автосохранение ко всем полям настроек
        for entry in [
            self.entry_api_key, self.entry_search_query, self.entry_region_id,
            self.entry_fit_score, self.entry_max_applies, self.entry_exclude_grades,
            self.entry_blacklist, self.entry_max_empty_pages, self.entry_max_skips,
            self.entry_last_page, self.entry_work_hours, self.entry_work_minutes
        ]:
            entry.bind("<KeyRelease>", lambda e: self.auto_save_settings())

        for txt in [self.txt_contacts, self.txt_special_wishes, self.txt_template_letter]:
            txt.bind("<KeyRelease>", lambda e: self.auto_save_settings())

        self.combobox_model.configure(command=lambda choice: self.auto_save_settings())
        self.combobox_region.configure(command=lambda choice: (self.on_region_selected(choice), self.auto_save_settings()))
        self.switch_resume_page.configure(command=self.auto_save_settings)

        # Применяем изначальное визуальное состояние полей на основе флага DISABLE_AI
        self.toggle_ai_settings_state()

    def toggle_ai_settings_state(self):
        """Включает/выключает поля ввода в зависимости от флага использования ИИ"""
        is_ai_enabled = self.switch_disable_ai.get()
        is_disabled = not is_ai_enabled
        if is_disabled:
            self.entry_api_key.configure(state="disabled", fg_color=Theme.BG_DARK, text_color=Theme.TEXT_MUTED, border_color=Theme.BG_DARK)
            self.combobox_model.configure(state="disabled", fg_color=Theme.BG_DARK, text_color=Theme.TEXT_MUTED, border_color=Theme.BG_DARK, button_color=Theme.BG_DARK, button_hover_color=Theme.BG_DARK)
            self.entry_fit_score.configure(state="disabled", fg_color=Theme.BG_DARK, text_color=Theme.TEXT_MUTED, border_color=Theme.BG_DARK)
            self.txt_special_wishes.configure(state="disabled", fg_color=Theme.BG_DARK, text_color=Theme.TEXT_MUTED, border_color=Theme.BG_DARK)
            self.txt_contacts.configure(state="disabled", fg_color=Theme.BG_DARK, text_color=Theme.TEXT_MUTED, border_color=Theme.BG_DARK)
            
            # Автоматически переключаем на шаблонное письмо и блокируем переключатель
            self.switch_use_template.select()
            self.switch_use_template.configure(state="disabled", text_color=Theme.TEXT_MUTED)
        else:
            self.entry_api_key.configure(state="normal", fg_color=Theme.BG_DARKEST, text_color=Theme.TEXT_PRIMARY, border_color=Theme.BORDER)
            self.combobox_model.configure(state="normal", fg_color=Theme.BG_DARKEST, text_color=Theme.TEXT_PRIMARY, border_color=Theme.BORDER, button_color=Theme.BG_ELEVATED, button_hover_color=Theme.BORDER_ACCENT)
            self.entry_fit_score.configure(state="normal", fg_color=Theme.BG_DARKEST, text_color=Theme.TEXT_PRIMARY, border_color=Theme.BORDER)
            self.txt_special_wishes.configure(state="normal", fg_color=Theme.BG_DARKEST, text_color=Theme.TEXT_PRIMARY, border_color=Theme.BORDER)
            self.txt_contacts.configure(state="normal", fg_color=Theme.BG_DARKEST, text_color=Theme.TEXT_PRIMARY, border_color=Theme.BORDER)
            
            self.switch_use_template.configure(state="normal", text_color=Theme.TEXT_SECONDARY)

        self.toggle_template_state()

    def toggle_template_state(self, *args):
        """Включает/выключает поле ввода шаблона письма"""
        # Если ИИ отключен, шаблон ВСЕГДА активен (так как это единственный способ отправить письмо)
        is_ai_enabled = self.switch_disable_ai.get()
        if not is_ai_enabled:
            self.txt_template_letter.configure(state="normal", fg_color=Theme.BG_DARKEST, text_color=Theme.TEXT_PRIMARY, border_color=Theme.BORDER)
            return

        # Если ИИ включен, то поле ввода шаблона активно только если выбран переключатель шаблонов
        use_template = self.switch_use_template.get()
        if use_template:
            self.txt_template_letter.configure(state="normal", fg_color=Theme.BG_DARKEST, text_color=Theme.TEXT_PRIMARY, border_color=Theme.BORDER)
        else:
            self.txt_template_letter.configure(state="disabled", fg_color=Theme.BG_DARK, text_color=Theme.TEXT_MUTED, border_color=Theme.BG_DARK)

    # ── Вспомогательные методы для создания виджетов настроек ──
    def _create_settings_card(self, parent, title, accent_color):
        """Создает стилизованную карточку настроек с цветным акцентом"""
        card = ctk.CTkFrame(
            parent, fg_color=Theme.BG_CARD, corner_radius=14, 
            border_width=1, border_color=Theme.BORDER
        )
        
        # Цветная полоска-акцент в заголовке
        header_bar = ctk.CTkFrame(card, fg_color=accent_color, height=3, corner_radius=0)
        header_bar.grid(row=0, column=0, columnspan=2, sticky="new", padx=20, pady=(14, 0))
        
        ctk.CTkLabel(
            card, text=title, 
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=accent_color
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(20, 8), sticky="w")

        return card

    def _create_field_label(self, parent, text, row, pady=8):
        ctk.CTkLabel(
            parent, text=text, 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Theme.TEXT_SECONDARY
        ).grid(row=row, column=0, padx=16, pady=pady, sticky="w")

    def _create_entry(self, parent, placeholder, row, pady=8):
        entry = ctk.CTkEntry(
            parent, fg_color=Theme.BG_DARKEST, 
            border_color=Theme.BORDER,
            placeholder_text=placeholder,
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_PRIMARY,
            corner_radius=10
        )
        entry.grid(row=row, column=1, padx=16, pady=pady, sticky="ew")
        return entry

    def _create_hint(self, parent, text, row, pady=(0, 10)):
        ctk.CTkLabel(
            parent, text=text, 
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=Theme.TEXT_MUTED
        ).grid(row=row, column=0, columnspan=2, padx=16, pady=pady, sticky="w")

    def on_region_selected(self, choice):
        code = self.regions_map[choice]
        if code == "custom":
            self.entry_region_id.configure(state="normal")
            self.entry_region_id.delete(0, "end")
        else:
            self.entry_region_id.configure(state="normal")
            self.entry_region_id.delete(0, "end")
            self.entry_region_id.insert(0, code)
            self.entry_region_id.configure(state="disabled")

    # ==========================================
    # 📝 Вкладка "Редактор резюме"
    # ==========================================
    def setup_resume_tab(self):
        self.tab_resume.configure(fg_color=Theme.BG_DARK)
        self.tab_resume.grid_rowconfigure(1, weight=1)
        self.tab_resume.grid_columnconfigure(0, weight=1)

        # Заголовок
        header_frame = ctk.CTkFrame(self.tab_resume, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=16, pady=(16, 6), sticky="ew")

        ctk.CTkLabel(
            header_frame, text="📄", 
            font=ctk.CTkFont(size=18)
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            header_frame, text="РЕДАКТОР СОДЕРЖИМОГО RESUME.TXT", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Theme.ACCENT_PRIMARY
        ).pack(side="left")

        # Текстовое поле резюме
        self.txt_resume = ctk.CTkTextbox(
            self.tab_resume, 
            font=ctk.CTkFont(family="Consolas", size=12), 
            fg_color=Theme.BG_DARKEST, border_color=Theme.BORDER, border_width=1,
            text_color=Theme.TEXT_PRIMARY, corner_radius=14
        )
        self.txt_resume.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")

        # Загружаем текущее резюме
        resume_text = Config.get_resume()
        if not resume_text and Config.RESUME_FILE.exists():
            # Если get_resume вернул пустоту из-за шаблона, загрузим файл напрямую
            try:
                with open(Config.RESUME_FILE, "r", encoding="utf-8") as f:
                    resume_text = f.read()
            except Exception:
                pass
        self.txt_resume.insert("1.0", resume_text)
        self.txt_resume.bind("<KeyRelease>", lambda e: self.auto_save_resume())

    # ==========================================
    # ⚙️ Логика сохранения настроек и файлов
    # ==========================================
    def auto_save_resume(self):
        text = self.txt_resume.get("1.0", "end-1c").strip()
        try:
            with open(Config.RESUME_FILE, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass

    def auto_save_settings(self):
        try:
            self.save_settings_env(show_toast_notification=False)
        except Exception:
            pass

    def save_resume_file(self):
        self.auto_save_resume()
        self.show_toast("✅ Успех", "Резюме успешно сохранено!")

    def save_settings_env(self, show_toast_notification=True):
        import tkinter as tk
        tk._default_root = self

        # Получаем данные из полей ввода
        api_key = self.entry_api_key.get().strip()
        model = self.combobox_model.get().strip()
        query = self.entry_search_query.get().strip()
        
        # Разрешаем disabled состояние для чтения
        self.entry_region_id.configure(state="normal")
        region_id = self.entry_region_id.get().strip()
        # Возвращаем disabled если это пресет
        if self.combobox_region.get() != "Указать вручную (код ID)":
            self.entry_region_id.configure(state="disabled")

        fit_score = self.entry_fit_score.get().strip()
        max_applies = self.entry_max_applies.get().strip()
        exclude_grades = self.entry_exclude_grades.get().strip()
        blacklist = self.entry_blacklist.get().strip()
        max_empty_pages = self.entry_max_empty_pages.get().strip()
        max_skips = self.entry_max_skips.get().strip()
        contacts = self.txt_contacts.get("1.0", "end-1c").strip()
        wishes = self.txt_special_wishes.get("1.0", "end-1c").strip()
        use_template = self.switch_use_template.get()
        template_text = self.txt_template_letter.get("1.0", "end-1c").strip()
        resume_from_last = self.switch_resume_page.get()
        disable_ai = not self.switch_disable_ai.get()
        confirm_applies = self.switch_confirm.get()
        last_page_val = self.entry_last_page.get().strip()
        work_hours = self.entry_work_hours.get().strip()
        work_minutes = self.entry_work_minutes.get().strip()

        # Формируем словарь новых параметров
        new_env_vars = {
            "GEMINI_API_KEY": api_key,
            "GEMINI_MODEL": model,
            "HH_SEARCH_QUERY": query,
            "HH_AREA": region_id,
            "MIN_FIT_SCORE": fit_score if fit_score.isdigit() else "7",
            "MAX_APPLIES_PER_RUN": max_applies if max_applies.isdigit() else "10",
            "EXCLUDE_GRADES": exclude_grades,
            "BLACKLIST_EMPLOYERS": blacklist,
            "MAX_EMPTY_PAGES": max_empty_pages if max_empty_pages.isdigit() else "0",
            "MAX_CONSECUTIVE_PROCESSED_SKIPS": max_skips if max_skips.isdigit() else "0",
            "USER_CONTACTS": contacts.replace("\n", "\\n"),
            "USER_SPECIAL_WISHES": wishes.replace("\n", "\\n"),
            "USE_TEMPLATE_LETTER": "True" if use_template else "False",
            "TEMPLATE_LETTER_TEXT": template_text.replace("\n", "\\n"),
            "DISABLE_AI": "True" if disable_ai else "False",
            "CONFIRM_APPLIES": "True" if confirm_applies else "False",
            "NIGHT_MODE": "True" if self.switch_night.get() else "False",
            "RESUME_FROM_LAST_PAGE": "True" if resume_from_last else "False",
            "LAST_SEARCH_PAGE": str(int(last_page_val) - 1) if last_page_val.isdigit() and int(last_page_val) > 0 else "0",
            "WORK_TIME_HOURS": work_hours if work_hours.isdigit() else "0",
            "WORK_TIME_MINUTES": work_minutes if work_minutes.isdigit() else "0"
        }

        # Читаем существующий .env и перезаписываем только нужные переменные (сохраняя комментарии)
        env_path = BASE_DIR / ".env"
        env_lines = []
        replaced_keys = set()

        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in line:
                        key = stripped.split("=")[0].strip()
                        if key in new_env_vars:
                            env_lines.append(f"{key}={new_env_vars[key]}\n")
                            replaced_keys.add(key)
                            continue
                    env_lines.append(line)
            except Exception:
                pass

        # Добавляем те переменные, которых не было в файле
        for key, val in new_env_vars.items():
            if key not in replaced_keys:
                env_lines.append(f"{key}={val}\n")

        # Записываем всё обратно в .env
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(env_lines)
            
            # Обновляем Config в текущей сессии
            Config.GEMINI_API_KEY = api_key
            Config.GEMINI_MODEL = model
            Config.HH_SEARCH_QUERY = query
            Config.HH_AREA = region_id
            Config.MIN_FIT_SCORE = int(fit_score) if fit_score.isdigit() else 7
            Config.MAX_APPLIES_PER_RUN = int(max_applies) if max_applies.isdigit() else 10
            Config.EXCLUDE_GRADES = [x.strip().lower() for x in exclude_grades.split(",") if x.strip()]
            Config.BLACKLIST_EMPLOYERS = [x.strip().lower() for x in blacklist.split(",") if x.strip()]
            Config.MAX_EMPTY_PAGES = int(max_empty_pages) if max_empty_pages.isdigit() else 0
            Config.MAX_CONSECUTIVE_PROCESSED_SKIPS = int(max_skips) if max_skips.isdigit() else 0
            Config.USER_CONTACTS = contacts
            Config.USER_SPECIAL_WISHES = wishes
            Config.USE_TEMPLATE_LETTER = use_template
            Config.TEMPLATE_LETTER_TEXT = template_text
            Config.DISABLE_AI = disable_ai
            Config.CONFIRM_APPLIES = confirm_applies
            Config.NIGHT_MODE = "True" if self.switch_night.get() else "False"
            Config.RESUME_FROM_LAST_PAGE = resume_from_last
            Config.LAST_SEARCH_PAGE = int(last_page_val) - 1 if last_page_val.isdigit() and int(last_page_val) > 0 else 0
            Config.WORK_TIME_HOURS = int(work_hours) if work_hours.isdigit() else 0
            Config.WORK_TIME_MINUTES = int(work_minutes) if work_minutes.isdigit() else 0

            # Синхронизируем новые лимиты на главной панели управления
            if hasattr(self, "entry_main_max_applies") and self.entry_main_max_applies.winfo_exists():
                self.entry_main_max_applies.delete(0, "end")
                self.entry_main_max_applies.insert(0, str(Config.MAX_APPLIES_PER_RUN))
                
            if hasattr(self, "entry_main_work_hours") and self.entry_main_work_hours.winfo_exists():
                self.entry_main_work_hours.delete(0, "end")
                self.entry_main_work_hours.insert(0, str(Config.WORK_TIME_HOURS))
                
            if hasattr(self, "entry_main_work_minutes") and self.entry_main_work_minutes.winfo_exists():
                self.entry_main_work_minutes.delete(0, "end")
                self.entry_main_work_minutes.insert(0, str(Config.WORK_TIME_MINUTES))

            self.write_log("[✔️] Настройки успешно сохранены и применены!\n", "success")
            if show_toast_notification:
                self.show_toast("✅ Успех", "Настройки успешно сохранены!")
        except Exception as e:
            self.write_log(f"[❌ Ошибка] Не удалось сохранить настройки в .env: {e}\n", "error")

    def reset_skipped_vacancies(self):
        import sqlite3
        db_path = BASE_DIR / "analytics.db"
        if not db_path.exists():
            self.write_log("❌ Ошибка: База данных analytics.db не найдена.\n", "error")
            self.show_toast("❌ Ошибка", "База данных аналитики не найдена.")
            return

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            
            # Удаляем только те записи, статус которых указывает на пропуски (т.е. кроме успешных и дубликатов)
            cur.execute("""
                DELETE FROM applications 
                WHERE status NOT IN ('Успешно отправлено', 'Успешно (Тестовый режим)', 'Уже откликался')
            """)
            
            deleted_count = cur.rowcount
            conn.commit()
            conn.close()

            self.write_log(f"[🧹] База данных очищена: сброшена история {deleted_count} пропущенных вакансий.\n", "success")
            self.show_toast("🧹 Очистка завершена", f"Успешно сброшена история {deleted_count} пропусков!\nПри следующем запуске бот переоценит их заново.")
        except Exception as e:
            self.write_log(f"❌ Ошибка при очистке БД: {e}\n", "error")
            self.show_toast("❌ Ошибка", f"Не удалось очистить БД: {e}")

    def toggle_night_mode(self):
        val = self.switch_night.get()
        Config.NIGHT_MODE = val
        self.write_log(f"[🌙] Автономный режим откликов: {'ВКЛЮЧЕН' if val else 'ВЫКЛЮЧЕН'}\n", "bot_action")
        # Сохраним изменение в .env автоматически
        self.save_settings_env(show_toast_notification=False)

    def toggle_confirm_mode(self):
        val = self.switch_confirm.get()
        Config.CONFIRM_APPLIES = val
        self.write_log(f"[🛡️] Подтверждение откликов вручную: {'ВКЛЮЧЕНО' if val else 'ВЫКЛЮЧЕНО'}\n", "bot_action")
        # Сохраним изменение в .env автоматически
        self.save_settings_env(show_toast_notification=False)

    # ==========================================
    # 🚀 Управление фоновыми процессами
    # ==========================================
    def start_dashboard(self):
        # Запускает Flask дашборд в фоновом потоке
        def run_flask():
            try:
                # Отключаем дебаг и релоадер для стабильной работы в потоке
                dashboard_flask_app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
            except Exception as e:
                self.write_log(f"[❌ Ошибка дашборда] Не удалось запустить сервер: {e}\n", "error")

        try:
            thread = threading.Thread(target=run_flask, daemon=True)
            thread.start()
            self.write_log("[✔️] Фоновый сервер аналитики дашборда запущен → http://localhost:5000\n", "success")
        except Exception as e:
            self.write_log(f"[⚠️] Не удалось запустить дашборд: {e}\n", "warning")

    def open_dashboard_url(self):
        try:
            import subprocess
            # Запускаем открытие браузера через независимый системный процесс start,
            # чтобы избежать фатальных багов CPython GIL при вызове webbrowser.open в Windows
            subprocess.Popen('start http://localhost:5000', shell=True)
        except Exception:
            try:
                import webbrowser
                webbrowser.open("http://localhost:5000")
            except Exception:
                pass

    def stop_bot(self):
        if not self.bot_running:
            return

        self.write_log("\n[⏹] Команда на остановку бота...\n", "warning")
        if self.bot_process:
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=3)
            except Exception:
                try:
                    self.bot_process.kill()
                except Exception:
                    pass
        self.reset_bot_ui_state()

    def toggle_pause(self):
        if Config.PAUSE_FILE.exists():
            try: Config.PAUSE_FILE.unlink()
            except: pass
            self.btn_pause.configure(text="⏸  Пауза")
            self.status_indicator.configure(text_color=Theme.STATUS_ACTIVE)
            self.status_text_label.configure(text="Выполняется", text_color=Theme.STATUS_ACTIVE)
            self.write_log("\n[▶️] Снято с паузы. Возобновление работы...\n", "success")
        else:
            try: Config.PAUSE_FILE.touch()
            except: pass
            self.btn_pause.configure(text="▶️  Возобновить")
            self.status_indicator.configure(text_color=Theme.STATUS_WARNING)
            self.status_text_label.configure(text="Пауза", text_color=Theme.STATUS_WARNING)
            self.write_log("\n[⏸️] Бот поставлен на паузу. Нажмите 'Возобновить' для продолжения.\n", "warning")


    def prompt_user_action(self):
        """Отображает зеленую кнопку 'Продолжить работу' в GUI при запросах или ошибках бота"""
        self.status_indicator.configure(text_color=Theme.STATUS_WARNING)
        self.status_text_label.configure(text="Требуется действие", text_color=Theme.STATUS_WARNING)
        if hasattr(self, "btn_resume"):
            self.btn_resume.pack(fill="x", padx=12, pady=(0, 6))
            self.btn_resume.configure(state="normal")
        try:
            self.bell()
        except Exception:
            pass

    def resume_bot(self):
        if self.bot_process and self.bot_running:
            self.write_log("\n[▶️] Отправка команды на продолжение работы...\n", "success")
            try:
                self.bot_process.stdin.write("\n")
                self.bot_process.stdin.flush()
                self.status_indicator.configure(text_color=Theme.STATUS_ACTIVE)
                self.status_text_label.configure(text="Выполняется", text_color=Theme.STATUS_ACTIVE)
                if hasattr(self, "btn_resume"):
                    self.btn_resume.pack_forget()
            except Exception as e:
                self.write_log(f"[❌ Ошибка при отправке команды продолжения]: {e}\n", "error")

    def reset_bot_ui_state(self):
        self.bot_running = False
        self.bot_process = None
        
        # Скрываем кнопки работы
        if hasattr(self, "running_controls_frame"):
            self.running_controls_frame.pack_forget()
        if hasattr(self, "btn_resume"):
            self.btn_resume.pack_forget()
            
        # Показываем кнопки входа и запуска
        if hasattr(self, "btn_run"):
            self.btn_run.pack(fill="x", padx=14, pady=(0, 6))
            self.btn_run.configure(state="normal")
        if hasattr(self, "btn_auth"):
            self.btn_auth.pack(fill="x", padx=14, pady=(0, 6))
            self.btn_auth.configure(state="normal")
        
        # Удаляем файл паузы если он остался
        if Config.PAUSE_FILE.exists():
            try: Config.PAUSE_FILE.unlink()
            except: pass
        
        # Индикатор в "Остановлен" (серый)
        self.status_indicator.configure(text_color=Theme.STATUS_OFF)
        self.status_text_label.configure(text="Остановлен", text_color=Theme.STATUS_OFF)

        # При остановке возвращаем на карточки общее итоговое число откликов из БД
        try:
            if hasattr(self, "lbl_stat_applies") and self.lbl_stat_applies.winfo_exists():
                self.lbl_stat_applies.configure(text=f"{Database.get_successful_applies_count()} / {Config.MAX_APPLIES_PER_RUN}")
        except Exception:
            pass

    def save_main_limits_to_env(self):
        """Считывает лимиты с главной панели, сохраняет их в .env и Config."""
        max_applies = self.entry_main_max_applies.get().strip()
        work_hours = self.entry_main_work_hours.get().strip()
        work_minutes = self.entry_main_work_minutes.get().strip()

        # Валидируем и обновляем в памяти Config
        Config.MAX_APPLIES_PER_RUN = int(max_applies) if max_applies.isdigit() else 10
        Config.WORK_TIME_HOURS = int(work_hours) if work_hours.isdigit() else 0
        Config.WORK_TIME_MINUTES = int(work_minutes) if work_minutes.isdigit() else 0

        # Формируем словарь для записи в .env
        new_vars = {
            "MAX_APPLIES_PER_RUN": str(Config.MAX_APPLIES_PER_RUN),
            "WORK_TIME_HOURS": str(Config.WORK_TIME_HOURS),
            "WORK_TIME_MINUTES": str(Config.WORK_TIME_MINUTES)
        }

        # Безопасно обновляем .env
        env_path = BASE_DIR / ".env"
        env_lines = []
        replaced_keys = set()

        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in line:
                        key = stripped.split("=")[0].strip()
                        if key in new_vars:
                            env_lines.append(f"{key}={new_vars[key]}\n")
                            replaced_keys.add(key)
                            continue
                    env_lines.append(line)
            except Exception:
                pass

        for key, val in new_vars.items():
            if key not in replaced_keys:
                env_lines.append(f"{key}={val}\n")

        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(env_lines)
            
            # Также синхронизируем поля во вкладке настроек
            if hasattr(self, "entry_max_applies") and self.entry_max_applies.winfo_exists():
                self.entry_max_applies.delete(0, "end")
                self.entry_max_applies.insert(0, str(Config.MAX_APPLIES_PER_RUN))
            
            if hasattr(self, "entry_work_hours") and self.entry_work_hours.winfo_exists():
                self.entry_work_hours.delete(0, "end")
                self.entry_work_hours.insert(0, str(Config.WORK_TIME_HOURS))
                
            if hasattr(self, "entry_work_minutes") and self.entry_work_minutes.winfo_exists():
                self.entry_work_minutes.delete(0, "end")
                self.entry_work_minutes.insert(0, str(Config.WORK_TIME_MINUTES))
        except Exception as e:
            print(f"Ошибка автоматического сохранения лимитов с главной панели: {e}")

    def start_bot_run(self):
        self.run_bot()

    def start_auth(self):
        if self.bot_running:
            self.write_log("[⚠️] Нельзя запустить авторизацию, пока работает бот!\n", "warning")
            return
            
        self.bot_running = True
        self.btn_run.pack_forget()
        self.btn_auth.pack_forget()
        self.running_controls_frame.pack(fill="x", padx=14, pady=(0, 6))
        
        # Меняем индикатор на "Активен" (голубой для авторизации)
        self.status_indicator.configure(text_color=Theme.ACCENT_CYAN)
        self.status_text_label.configure(text="Авторизация", text_color=Theme.ACCENT_CYAN)
        
        if getattr(sys, 'frozen', False):
            args = [sys.executable, "--bot-mode", "--gui-mode", "--auth"]
        else:
            args = [sys.executable, "-u", "main.py", "--gui-mode", "--auth"]
            
        self.write_log(f"\n[🔑] ЗАПУСК ручной авторизации...\n", "bot_action")
        self.write_log("Откроется окно браузера hh.ru. Пожалуйста, выполните вход.\n", "info")
        self.write_log("После успешного входа нажмите зеленую кнопку 'Продолжить работу' здесь в GUI!\n", "warning")
        
        try:
            self.bot_process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )
            
            self.log_thread = threading.Thread(target=self.read_bot_logs, daemon=True)
            self.log_thread.start()
        except Exception as e:
            self.write_log(f"[❌ Ошибка запуска авторизации]: {e}\n", "error")
            self.reset_bot_ui_state()

    def run_bot(self):
        if self.bot_running:
            return

        # Сохраняем свежие лимиты с главной панели перед запуском процесса бота
        self.save_main_limits_to_env()

        # ── Валидация перед запуском ──
        api_key = Config.GEMINI_API_KEY
        if (not api_key or not api_key.strip()) and not Config.DISABLE_AI:
            self.write_log("[❌ Ошибка запуска]: Не указан Gemini API-ключ! Пожалуйста, перейдите во вкладку «Настройки бота» и введите ключ.\n", "error")
            self.show_toast("⚠️ Ошибка запуска", "Заполните API-ключ Gemini во вкладке «Настройки»!")
            return

        if not Config.DISABLE_AI:
            resume = Config.get_resume()
            if not resume or not resume.strip() or "=== ВСТАВЬТЕ СЮДА ВАШЕ РЕЗЮМЕ ===" in resume:
                self.write_log("[❌ Ошибка запуска]: Ваше резюме не заполнено! Пожалуйста, заполните его во вкладке «Редактор резюме».\n", "error")
                self.show_toast("⚠️ Ошибка запуска", "Заполните резюме во вкладке «Редактор резюме»!")
                return

        self.bot_running = True
        self.bot_start_time = time.time()
        self.current_applied_count = 0
        
        # Сбрасываем плашки KPI перед стартом
        if hasattr(self, "lbl_stat_applies") and self.lbl_stat_applies.winfo_exists():
            self.lbl_stat_applies.configure(text=f"0 / {Config.MAX_APPLIES_PER_RUN}")
        if hasattr(self, "lbl_stat_time") and self.lbl_stat_time.winfo_exists():
            self.lbl_stat_time.configure(text="00:00:00")
        if hasattr(self, "lbl_stat_score") and self.lbl_stat_score.winfo_exists():
            self.lbl_stat_score.configure(text="— / 10")
        if hasattr(self, "lbl_stat_mode") and self.lbl_stat_mode.winfo_exists():
            self.lbl_stat_mode.configure(text="Смарт-динамика")
        
        # Динамически переключаем кнопки управления
        self.btn_run.pack_forget()
        self.btn_auth.pack_forget()
        self.running_controls_frame.pack(fill="x", padx=14, pady=(0, 6))
        self.btn_pause.configure(text="⏸ Пауза")

        # Удаляем файл паузы перед стартом
        if Config.PAUSE_FILE.exists():
            try: Config.PAUSE_FILE.unlink()
            except: pass
        if hasattr(self, "btn_resume"):
            self.btn_resume.pack_forget()
        
        # Меняем индикатор на "Активен" (зеленый)
        self.status_indicator.configure(text_color=Theme.STATUS_ACTIVE)
        self.status_text_label.configure(text="Выполняется", text_color=Theme.STATUS_ACTIVE)

        # Выбираем аргументы запуска в зависимости от режима EXE
        if getattr(sys, 'frozen', False):
            # В скомпилированном EXE вызываем сам EXE с флагом --bot-mode
            args = [sys.executable, "--bot-mode", "--gui-mode", "--run"]
        else:
            # В режиме разработки вызываем python main.py
            args = [sys.executable, "-u", "main.py", "--gui-mode", "--run"]

        self.write_log(f"\n[🚀] ЗАПУСК автоотклик-бота...\n", "bot_action")
        
        try:
            self.bot_process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )
            
            # Запускаем поток для чтения логов из stdout
            self.log_thread = threading.Thread(target=self.read_bot_logs, daemon=True)
            self.log_thread.start()
        except Exception as e:
            self.write_log(f"[❌ Ошибка запуска бота]: {e}\n", "error")
            self.reset_bot_ui_state()

    def update_session_timer(self):
        """Динамический отсчёт времени работы бота в карточке KPI"""
        try:
            if self.bot_running and self.bot_start_time:
                elapsed = int(time.time() - self.bot_start_time)
                hrs = elapsed // 3600
                mins = (elapsed % 3600) // 60
                secs = elapsed % 60
                if hasattr(self, "lbl_stat_time") and self.lbl_stat_time.winfo_exists():
                    self.lbl_stat_time.configure(text=f"{hrs:02d}:{mins:02d}:{secs:02d}")
            elif not self.bot_running:
                total_sec = Database.get_total_duration()
                hrs = total_sec // 3600
                mins = (total_sec % 3600) // 60
                secs = total_sec % 60
                if hasattr(self, "lbl_stat_time") and self.lbl_stat_time.winfo_exists():
                    self.lbl_stat_time.configure(text=f"{hrs:02d}:{mins:02d}:{secs:02d}")
        except Exception:
            pass
        self.after(1000, self.update_session_timer)

    def read_bot_logs(self):
        # Построчно считывает вывод процесса бота
        import re
        while self.bot_process and self.bot_running:
            line = self.bot_process.stdout.readline()
            if not line:
                break
            
            # Очищаем ANSI-цвета
            clean_line = ANSI_ESCAPE.sub('', line)
            
            # ── Динамическое обновление карточек KPI ──
            try:
                # 1. Счётчик откликов
                match_app = re.search(r'🚀\s*\[(\d+)/(\d+)\]', clean_line)
                if match_app:
                    curr = match_app.group(1)
                    max_a = match_app.group(2)
                    self.after(0, lambda c=curr, m=max_a: self.lbl_stat_applies.configure(text=f"{c} / {m}"))
                elif "Успешно отправлено" in clean_line or "Отправлен отклик" in clean_line or "Успешно (" in clean_line:
                    self.current_applied_count += 1
                    curr_c = self.current_applied_count
                    self.after(0, lambda c=curr_c: self.lbl_stat_applies.configure(text=f"{c} / {Config.MAX_APPLIES_PER_RUN}"))

                # 2. Оценка соответствия
                match_score = re.search(r'Оценка соответствия\]:\s*(\d+)', clean_line)
                if match_score:
                    sc = match_score.group(1)
                    self.after(0, lambda s=sc: self.lbl_stat_score.configure(text=f"{s} / 10"))

                # 3. Задержка
                match_delay = re.search(r'(?:Ожидание|Задержка)[^\d]*(\d+\.?\d*)\s*сек', clean_line)
                if match_delay:
                    d_val = match_delay.group(1)
                    self.after(0, lambda d=d_val: self.lbl_stat_mode.configure(text=f"{d} сек"))
                elif "Человеческий перерыв" in clean_line:
                    self.after(0, lambda: self.lbl_stat_mode.configure(text="Перерыв ☕"))
            except Exception:
                pass
            
            # Определяем тег цвета по содержимому строки
            tag = None
            if "✔" in clean_line or "Успешно" in clean_line or "успешно" in clean_line:
                tag = "success"
            elif "⚠" in clean_line or "Предупреждение" in clean_line or "ПРИОСТАНОВЛЕН" in clean_line:
                tag = "warning"
            elif "❌" in clean_line or "Ошибка" in clean_line or "ошибка" in clean_line:
                tag = "error"
            elif "🚀" in clean_line or "🧪" in clean_line or "📝" in clean_line:
                tag = "bot_action"
            elif "ℹ" in clean_line:
                tag = "info"
            
            # Если строка содержит сигнал о вводе пользователя (ожидание нажатия Enter)
            if "Нажмите ENTER" in clean_line or "🚨 СКРИПТ ПРИОСТАНОВЛЕН" in clean_line or "ТРЕБУЕТСЯ ПОДТВЕРЖДЕНИЕ" in clean_line:
                self.after(0, self.prompt_user_action)
                tag = "warning"
                
            self.write_log(clean_line, tag)

        # Дожидаемся завершения процесса
        if self.bot_process:
            self.bot_process.wait()
        
        self.write_log("\n[🏁] Процесс автоотклика завершил работу.\n", "info")
        self.reset_bot_ui_state()



    # ==========================================
    # 📺 Вспомогательные методы
    # ==========================================
    def write_log(self, text, tag=None):
        """Безопасно пишет логи из фоновых потоков в GUI виджет с цветовой подсветкой и дублирует в терминал"""
        # Трансляция логов и ошибок напрямую в терминал/консоль
        try:
            target_stream = sys.stderr if tag == "error" else sys.stdout
            target_stream.write(text if text.endswith('\n') else text + '\n')
            target_stream.flush()
        except Exception:
            pass

        def append():
            if hasattr(self, "txt_log") and self.txt_log._textbox.winfo_exists():
                if tag:
                    # Вставляем текст с цветным тегом
                    self.txt_log._textbox.insert("end", text, tag)
                else:
                    self.txt_log._textbox.insert("end", text)
                self.txt_log.see("end")
        self.after(0, append)

    def clear_console(self):
        self.txt_log.delete("1.0", "end")

    def block_input(self, event):
        # Разрешаем копирование (Ctrl+C, Ctrl+С на рус) и выделение всего (Ctrl+A, Ctrl+Ф на рус)
        # event.state & 0x0004 означает, что зажат Ctrl (Control)
        if event.state & 0x0004 and event.keysym.lower() in ['c', 'v', 'a', 'x', 'с', 'м', 'ф', 'ч']:
            if event.keysym.lower() in ['c', 'с', 'a', 'ф']:
                return None  # Разрешаем Ctrl+C и Ctrl+A
            else:
                return "break"  # Блокируем Ctrl+V (вставку) и Ctrl+X (вырезание)
        
        # Разрешаем навигацию стрелочками и прокрутку
        if event.keysym in ['Left', 'Right', 'Up', 'Down', 'Prior', 'Next', 'Home', 'End']:
            return None
            
        return "break" # Все остальные клавиши (ввод текста, Backspace, Delete) блокируем

    def copy_selected_log(self):
        try:
            selected_text = self.txt_log.get("sel.first", "sel.last")
            self.clipboard_clear()
            self.clipboard_append(selected_text)
        except Exception:
            pass

    def copy_all_logs(self):
        try:
            all_text = self.txt_log.get("1.0", "end-1c")
            self.clipboard_clear()
            self.clipboard_append(all_text)
        except Exception:
            pass

    def show_log_context_menu(self, event):
        try:
            # Проверяем, есть ли выделение
            has_selection = False
            try:
                self.txt_log.get("sel.first", "sel.last")
                has_selection = True
            except Exception:
                pass
            
            # Включаем/выключаем пункт в зависимости от наличия выделения
            if has_selection:
                self.log_context_menu.entryconfigure("Копировать выделенное", state="normal")
            else:
                self.log_context_menu.entryconfigure("Копировать выделенное", state="disabled")
                
            self.log_context_menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass
        finally:
            try:
                self.log_context_menu.grab_release()
            except Exception:
                pass

    def show_toast(self, title, message):
        """Премиальное всплывающее уведомление с автозакрытием"""
        import tkinter as tk
        tk._default_root = self
        toast = ctk.CTkToplevel(self)
        toast.title("")
        toast.geometry("360x130")
        toast.resizable(False, False)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=Theme.BG_CARD)
        toast.overrideredirect(True)  # Без рамки окна Windows
        
        # Центрируем поверх главного окна
        x = self.winfo_x() + (self.winfo_width() // 2) - 180
        y = self.winfo_y() + (self.winfo_height() // 2) - 65
        toast.geometry(f"+{x}+{y}")

        # Контейнер с рамкой
        container = ctk.CTkFrame(
            toast, fg_color=Theme.BG_CARD, 
            corner_radius=16, border_width=1, border_color=Theme.ACCENT_PRIMARY
        )
        container.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(
            container, text=title, 
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Theme.ACCENT_PRIMARY
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            container, text=message, 
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_SECONDARY
        ).pack(pady=(0, 12))

        ctk.CTkButton(
            container, text="Понятно", width=100, height=30,
            fg_color=Theme.BTN_VIOLET, hover_color=Theme.BTN_VIOLET_HOVER,
            corner_radius=10, font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffffff",
            command=toast.destroy
        ).pack()

        # Автозакрытие через 3 секунды
        toast.after(3000, lambda: toast.destroy() if toast.winfo_exists() else None)

    def on_closing(self):
        # Корректное завершение фоновых процессов при закрытии
        if self.bot_process:
            try:
                self.bot_process.terminate()
                self.bot_process.wait(timeout=2)
            except Exception:
                try:
                    self.bot_process.kill()
                except Exception:
                    pass

        self.destroy()

def show_instant_splash():
    """Мгновенное окно загрузки при щелчке по приложению с иконкой image.ico"""
    try:
        import tkinter as tk
        from PIL import Image, ImageTk
    except Exception:
        return None

    try:
        splash = tk.Tk()
        splash.overrideredirect(True)
        splash.configure(bg="#09090b")
        
        width, height = 420, 240
        screen_w = splash.winfo_screenwidth()
        screen_h = splash.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        splash.geometry(f"{width}x{height}+{x}+{y}")
        
        icon_path = get_resource_path("image.ico")
        if icon_path.exists():
            try:
                splash.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Стеклянная рамка со светящейся границей
        frame = tk.Frame(splash, bg="#141417", highlightbackground="#6366f1", highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        # Отрисовка иконки image.ico
        img_ok = False
        if icon_path.exists():
            try:
                img = Image.open(icon_path).resize((52, 52), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                img_label = tk.Label(frame, image=photo, bg="#141417")
                img_label.image = photo
                img_label.pack(pady=(22, 6))
                img_ok = True
            except Exception:
                pass
                
        if not img_ok:
            lbl_logo = tk.Label(frame, text="🤖", font=("Segoe UI Emoji", 30), bg="#141417", fg="#6366f1")
            lbl_logo.pack(pady=(18, 4))

        lbl_title = tk.Label(frame, text="VibeClickerHH.ru", font=("Segoe UI", 16, "bold"), bg="#141417", fg="#ececf1")
        lbl_title.pack()

        lbl_sub = tk.Label(frame, text="Загрузка компонентов и запуск системы...", font=("Segoe UI", 10), bg="#141417", fg="#8b5cf6")
        lbl_sub.pack(pady=(4, 16))

        # Анимированный неоновый прогресс-бар
        pbar = tk.Canvas(frame, width=320, height=4, bg="#27272a", highlightthickness=0)
        pbar.pack(pady=(0, 20))
        bar_rect = pbar.create_rectangle(0, 0, 90, 4, fill="#6366f1", width=0)

        def animate_pbar(pos=0):
            try:
                if splash.winfo_exists():
                    new_pos = (pos + 10) % 340
                    pbar.coords(bar_rect, new_pos, 0, new_pos + 90, 4)
                    splash.after(35, animate_pbar, new_pos)
            except Exception:
                pass

        animate_pbar()
        splash.update()
        return splash
    except Exception:
        return None

if __name__ == "__main__":
    # ── 1. Перехват флага запуска в режиме бота-подпроцесса ──
    if len(sys.argv) > 1 and "--bot-mode" in sys.argv:
        # Убираем --bot-mode, чтобы argparse в main.py не ругался
        sys.argv.remove("--bot-mode")
        # Импортируем и запускаем main.py
        import main
        try:
            main.main()
        except KeyboardInterrupt:
            sys.exit(0)
        sys.exit(0)

    # ── Показываем мгновенное окно загрузки ──
    splash_win = show_instant_splash()

    # ── Инициализируем схему базы данных ──
    Database.init_db()

    # ── 2. Запуск основного GUI ──
    try:
        # Фикс иконки на панели задач Windows
        if os.name == 'nt':
            try:
                import ctypes
                myappid = 'ru.vibeclickerhh.app.v1'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass

        app = App()
        import tkinter as tk
        tk._default_root = app
        
        # Закрываем мгновенное окно загрузки после инициализации главного окна
        if splash_win:
            try:
                splash_win.destroy()
            except Exception:
                pass
            tk._default_root = app

        # Закрываем PyInstaller splash screen, если он есть
        try:
            import pyi_splash
            pyi_splash.close()
        except ImportError:
            pass
            
        app.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)

