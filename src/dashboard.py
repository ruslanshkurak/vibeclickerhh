import os
import sys
from pathlib import Path

# Добавляем корень проекта в пути поиска модулей для возможности независимого запуска
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.database import Database

def generate_html_dashboard():
    records = Database.get_all_records()
    
    total = len(records)
    applied = sum(1 for r in records if r.get("status") and "Успешно" in r.get("status"))
    skipped = total - applied

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Аналитика откликов</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 text-gray-800 p-8">
    <div class="max-w-7xl mx-auto">
        <h1 class="text-3xl font-bold mb-6">Статистика откликов hh.ru</h1>
        
        <div class="grid grid-cols-3 gap-6 mb-8">
            <div class="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-500">
                <h3 class="text-gray-500 text-sm font-semibold uppercase">Всего обработано</h3>
                <p class="text-3xl font-bold text-gray-800">{total}</p>
            </div>
            <div class="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-500">
                <h3 class="text-gray-500 text-sm font-semibold uppercase">Успешные отклики</h3>
                <p class="text-3xl font-bold text-gray-800">{applied}</p>
            </div>
            <div class="bg-white p-6 rounded-lg shadow-md border-l-4 border-yellow-500">
                <h3 class="text-gray-500 text-sm font-semibold uppercase">Пропущено / Ошибки</h3>
                <p class="text-3xl font-bold text-gray-800">{skipped}</p>
            </div>
        </div>

        <div class="bg-white rounded-lg shadow-md overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Дата</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Вакансия</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Оценка ИИ</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Статус</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Детали</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
"""
    for r in records:
        status = r.get("status", "") or ""
        if "Успешно" in status:
            status_color = "bg-green-100 text-green-800"
        elif "Низкая оценка" in status:
            status_color = "bg-yellow-100 text-yellow-800"
        elif "Черный список" in status:
            status_color = "bg-gray-100 text-gray-800"
        else:
            status_color = "bg-red-100 text-red-800"

        title = r.get("title") or f"Вакансия {r.get('job_id')}"
        company = r.get("company", "") or ""
        url = r.get("url") or "#"
        score = r.get("ai_score")
        score_text = str(score) if score is not None else "-"
        
        # Экранируем спецсимволы для безопасной вставки в alert()
        reason = (r.get("ai_reason") or "").replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\\n', '\\\\n').replace('\\r', '')
        letter = (r.get("cover_letter") or "").replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"').replace('\\n', '\\\\n').replace('\\r', '')
        # Заменяем реальные переносы строк на \n для JS
        reason = reason.replace('\n', '\\n')
        letter = letter.replace('\n', '\\n')
        
        score_color = "bg-gray-100 text-gray-800"
        if score is not None:
            score_color = "bg-green-100 text-green-800" if int(score) >= 7 else "bg-red-100 text-red-800"

        row = f"""
                    <tr>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{r.get('timestamp', '').split('.')[0]}</td>
                        <td class="px-6 py-4">
                            <a href="{url}" target="_blank" class="text-blue-600 hover:underline font-medium">{title}</a>
                            <div class="text-sm text-gray-500">{company}</div>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {score_color}">
                                {score_text}/10
                            </span>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full {status_color}">
                                {status}
                            </span>
                        </td>
                        <td class="px-6 py-4 text-sm font-medium">
                            <button onclick="alert('Решение ИИ:\\n{reason}\\n\\nПисьмо:\\n{letter}')" class="text-indigo-600 hover:text-indigo-900 bg-indigo-50 px-3 py-1 rounded">Посмотреть</button>
                        </td>
                    </tr>
"""
        html += row

    html += """
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
    
    dashboard_path = Path(__file__).resolve().parent.parent / "dashboard.html"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    return str(dashboard_path)

if __name__ == "__main__":
    path = generate_html_dashboard()
    print(f"Дашборд сгенерирован по пути: {path}")
