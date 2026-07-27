import sqlite3
from pathlib import Path

def reset_skipped():
    db_path = Path("analytics.db")
    if not db_path.exists():
        print("❌ База данных analytics.db не найдена в текущей папке.")
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Удаляем все записи, статус которых указывает на пропуск или ошибку
        cur.execute("""
            DELETE FROM applications 
            WHERE status NOT IN ('Успешно отправлено', 'Успешно (Тестовый режим)', 'Уже откликался')
        """)
        
        deleted_count = cur.rowcount
        conn.commit()
        conn.close()
        
        print(f"🎉 Успешно сброшено {deleted_count} пропущенных вакансий из базы данных!")
        print("При следующем запуске бот заново проанализирует эти вакансии.")
    except Exception as e:
        print(f"❌ Произошла ошибка при очистке базы данных: {e}")

if __name__ == "__main__":
    reset_skipped()
