import os
import sys
import shutil
import stat
import subprocess
from pathlib import Path

def remove_readonly(func, path, excinfo):
    """Сбрасывает атрибут Read-Only и пробует удалить файл снова (для Windows)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def run_cmd(args, cwd=None):
    """Вспомогательная функция для запуска команд."""
    print(f"Running: {' '.join(args)}")
    subprocess.run(args, check=True, cwd=cwd)

def build_in_venv():
    root_dir = Path(__file__).resolve().parent
    venv_dir = root_dir / ".venv_build"
    
    print("=== Начало сборки в чистом виртуальном окружении ===")
    
    # 1. Создаем чистое виртуальное окружение
    if venv_dir.exists():
        print("Удаление старой папки виртуального окружения...")
        shutil.rmtree(venv_dir, onerror=remove_readonly)
        
    print("1. Создание виртуального окружения...")
    run_cmd([sys.executable, "-m", "venv", str(venv_dir)])
    
    # Определение путей к python и pip в виртуальном окружении на Windows
    venv_python = str(venv_dir / "Scripts" / "python.exe")
    venv_pip = str(venv_dir / "Scripts" / "pip.exe")
    
    # 2. Обновляем pip и устанавливаем необходимые зависимости
    print("\n2. Установка зависимостей (это займет некоторое время)...")
    run_cmd([venv_python, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Устанавливаем зависимости из requirements.txt
    run_cmd([venv_pip, "install", "-r", str(root_dir / "requirements.txt")])
    
    # Устанавливаем PyInstaller в это окружение
    run_cmd([venv_pip, "install", "pyinstaller"])
    
    # 3. Находим путь к ресурсам customtkinter для корректной упаковки
    print("\n3. Определение ресурсов CustomTkinter...")
    ctk_dir = ""
    try:
        res = subprocess.run([venv_python, "-c", "import customtkinter; print(customtkinter.__path__[0])"], capture_output=True, text=True, check=True)
        ctk_dir = res.stdout.strip()
    except Exception as e:
        print(f"Предупреждение: Не удалось автоматически найти путь customtkinter: {e}")

    print("\n4. Запуск PyInstaller для сборки EXE...")
    pyinstaller_bin = str(venv_dir / "Scripts" / "pyinstaller.exe")
    
    build_cmd = [
        pyinstaller_bin,
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--icon=image.ico",
        "--add-data=image.ico;.",
    ]

    if ctk_dir:
        build_cmd.append(f"--add-data={ctk_dir};customtkinter")

    if (root_dir / "splash.png").exists():
        build_cmd.append("--splash=splash.png")

    if (root_dir / "resume.txt.example").exists():
        build_cmd.append("--add-data=resume.txt.example;.")

    build_cmd.append("gui_app.py")
    
    try:
        run_cmd(build_cmd, cwd=str(root_dir))
        print("\n🎉 Сборка успешно завершена!")
        
        exe_path = root_dir / "dist" / "gui_app.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Итоговый размер EXE-файла: {size_mb:.2f} MB")
            print(f"Файл находится по пути: {exe_path.resolve()}")
            
    except Exception as e:
        print(f"\n❌ Ошибка во время сборки: {e}")
    finally:
        # 4. Очистка временных файлов
        print("\n4. Очистка временных файлов сборщика...")
        build_dir = root_dir / "build"
        spec_file = root_dir / "gui_app.spec"
        
        if build_dir.exists():
            shutil.rmtree(build_dir, onerror=remove_readonly)
            print("- Папка 'build' удалена.")
        if spec_file.exists():
            spec_file.unlink()
            print("- Файл 'gui_app.spec' удален.")
            
        # Удаляем виртуальное окружение
        if venv_dir.exists():
            print("- Удаление временного виртуального окружения...")
            try:
                shutil.rmtree(venv_dir, onerror=remove_readonly)
                print("- Временное виртуальное окружение удалено.")
            except Exception as e:
                print(f"  Не удалось автоматически удалить .venv_build (возможно заблокировано процессами): {e}")
                print("  Вы можете удалить папку .venv_build вручную.")

if __name__ == "__main__":
    build_in_venv()
