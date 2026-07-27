import os
import sys
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify

# Убеждаемся, что модули из src доступны
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.database import Database

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru" class="dark">
<head>
    <meta charset="UTF-8">
    <title>VibeClickerHH.ru Dashboard</title>
    <!-- Google Fonts Inter -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['Inter', 'sans-serif'],
                    }
                }
            }
        }
    </script>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #020617; /* Slate 950 */
        }
        /* Custom scrollbar for premium feel */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #020617;
        }
        ::-webkit-scrollbar-thumb {
            background: #1e293b;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #334155;
        }
    </style>
    <script>
        async function updateStatus(jobId, selectElement) {
            const status = selectElement.value;
            selectElement.classList.add('opacity-50');
            try {
                const response = await fetch('/api/update_status', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({job_id: jobId, status: status})
                });
                if (response.ok) {
                    selectElement.classList.add('border-green-500', 'bg-green-500/10');
                    setTimeout(() => selectElement.classList.remove('border-green-500', 'bg-green-500/10'), 600);
                }
            } catch(e) {
                alert('Ошибка сохранения');
            } finally {
                selectElement.classList.remove('opacity-50');
            }
        }

        function updateBotStatusColor(selectElement, status) {
            // Удаляем старые цвета
            selectElement.classList.remove('bg-green-500/10', 'text-green-400', 'border-green-500/30',
                                            'bg-yellow-500/10', 'text-yellow-400', 'border-yellow-500/30',
                                            'bg-slate-500/10', 'text-slate-400', 'border-slate-500/30',
                                            'bg-red-500/10', 'text-red-400', 'border-red-500/30');
            
            if (status.includes('Успешно')) {
                selectElement.classList.add('bg-green-500/10', 'text-green-400', 'border-green-500/30');
            } else if (status.includes('Низкая оценка')) {
                selectElement.classList.add('bg-yellow-500/10', 'text-yellow-400', 'border-yellow-500/30');
            } else if (status.includes('Черный список')) {
                selectElement.classList.add('bg-slate-500/10', 'text-slate-400', 'border-slate-500/30');
            } else {
                selectElement.classList.add('bg-red-500/10', 'text-red-400', 'border-red-500/30');
            }
        }

        async function updateBotStatus(jobId, selectElement) {
            const status = selectElement.value;
            selectElement.classList.add('opacity-50');
            try {
                const response = await fetch('/api/update_bot_status', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({job_id: jobId, status: status})
                });
                if (response.ok) {
                    updateBotStatusColor(selectElement, status);
                    
                    const row = selectElement.closest('tr');
                    const isSkipped = (status.includes('Пропущено') && !status.includes('Анкета/Тест')) ? 'true' : 'false';
                    const isManual = (status.includes('Требует ручной проверки') || status.includes('Анкета/Тест')) ? 'true' : 'false';
                    row.setAttribute('data-is-skipped', isSkipped);
                    row.setAttribute('data-is-manual', isManual);
                    
                    filterRows();
                    
                    selectElement.classList.add('border-green-500', 'bg-green-500/20');
                    setTimeout(() => selectElement.classList.remove('border-green-500', 'bg-green-500/20'), 600);
                }
            } catch(e) {
                alert('Ошибка сохранения');
            } finally {
                selectElement.classList.remove('opacity-50');
            }
        }

        function enableNotesEdit(jobId) {
            const viewDiv = document.getElementById(`view-notes-${jobId}`);
            const editDiv = document.getElementById(`edit-notes-${jobId}`);
            const textarea = document.getElementById(`textarea-notes-${jobId}`);
            
            viewDiv.classList.add('hidden');
            editDiv.classList.remove('hidden');
            textarea.focus();
            
            // Устанавливаем курсор в конец текста
            const val = textarea.value;
            textarea.value = '';
            textarea.value = val;
        }

        function cancelNotesEdit(jobId) {
            const viewDiv = document.getElementById(`view-notes-${jobId}`);
            const editDiv = document.getElementById(`edit-notes-${jobId}`);
            
            editDiv.classList.add('hidden');
            viewDiv.classList.remove('hidden');
        }

        async function saveInlineNotes(jobId) {
            const viewDiv = document.getElementById(`view-notes-${jobId}`);
            const editDiv = document.getElementById(`edit-notes-${jobId}`);
            const textarea = document.getElementById(`textarea-notes-${jobId}`);
            const statusSpan = document.getElementById(`status-notes-${jobId}`);
            const notesText = textarea.value.trim();
            
            statusSpan.innerText = 'Сохраняю...';
            statusSpan.classList.remove('text-red-400', 'text-green-400');
            statusSpan.classList.add('text-indigo-400');
            statusSpan.style.opacity = '1';
            
            textarea.disabled = true;
            try {
                const response = await fetch('/api/update_notes', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({job_id: jobId, notes: notesText})
                });
                
                if (response.ok) {
                    statusSpan.innerText = 'Сохранено ✓';
                    statusSpan.classList.remove('text-indigo-400');
                    statusSpan.classList.add('text-green-400');
                    
                    // Обновляем текст в режиме просмотра
                    let innerHTML = '';
                    if (notesText) {
                        innerHTML = `
                            <p id="text-notes-${jobId}" class="text-xs text-slate-300 break-words leading-relaxed line-clamp-3 group-hover:text-indigo-300 transition-colors">${escapeHTML(notesText)}</p>
                            <span class="text-[10px] text-slate-500 mt-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center space-x-1">
                                <span>✏️ Кликните для редактирования</span>
                            </span>
                        `;
                    } else {
                        innerHTML = `
                            <span class="inline-flex items-center space-x-1.5 text-xs text-slate-500 group-hover:text-indigo-400 font-medium transition-colors">
                                <span>➕</span>
                                <span>Добавить заметку</span>
                            </span>
                        `;
                    }
                    viewDiv.innerHTML = innerHTML;
                    
                    // Плавное закрытие редактора через 800мс
                    setTimeout(() => {
                        statusSpan.style.opacity = '0';
                        editDiv.classList.add('hidden');
                        viewDiv.classList.remove('hidden');
                    }, 800);
                } else {
                    throw new Error('Ошибка сервера');
                }
            } catch(e) {
                statusSpan.innerText = 'Ошибка ❌';
                statusSpan.classList.remove('text-indigo-400');
                statusSpan.classList.add('text-red-400');
                setTimeout(() => {
                    statusSpan.style.opacity = '0';
                }, 2000);
            } finally {
                textarea.disabled = false;
            }
        }

        function escapeHTML(str) {
            return str
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        async function deleteRow(jobId, btnElement) {
            if (!confirm('Точно удалить эту вакансию из базы?')) return;
            
            btnElement.disabled = true;
            try {
                const response = await fetch('/api/delete_vacancy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({job_id: jobId})
                });
                if (response.ok) {
                    const row = btnElement.closest('tr');
                    row.style.opacity = '0';
                    setTimeout(() => row.remove(), 300);
                } else {
                    alert('Не удалось удалить');
                    btnElement.disabled = false;
                }
            } catch(e) {
                alert('Ошибка при удалении');
                btnElement.disabled = false;
            }
        }
        
        let currentCardFilter = 'all';

        function setCardFilter(filterType, cardElement) {
            if (currentCardFilter === filterType && filterType !== 'all') {
                currentCardFilter = 'all';
                // Снимаем выделение со всех карточек
                document.querySelectorAll('.stats-card').forEach(card => {
                    card.classList.remove('ring-2', 'ring-indigo-500', 'ring-green-500', 'ring-red-500', 'ring-yellow-500', 'ring-cyan-500', 'ring-violet-500', 'ring-emerald-500');
                });
                // По умолчанию выделяем карточку "Всего обработано" (первая карточка)
                const allCard = document.querySelector('.stats-card');
                if (allCard) {
                    allCard.classList.add('ring-2', 'ring-indigo-500');
                }
            } else {
                currentCardFilter = filterType;
                
                // Снимаем выделение со всех карточек
                document.querySelectorAll('.stats-card').forEach(card => {
                    card.classList.remove('ring-2', 'ring-indigo-500', 'ring-green-500', 'ring-red-500', 'ring-yellow-500', 'ring-cyan-500', 'ring-violet-500', 'ring-emerald-500');
                });
                
                if (cardElement) {
                    let ringColor = 'ring-indigo-500';
                    if (filterType === 'applied') ringColor = 'ring-green-500';
                    if (filterType === 'manual') ringColor = 'ring-red-500';
                    if (filterType === 'skipped') ringColor = 'ring-yellow-500';
                    if (filterType === 'today') ringColor = 'ring-cyan-500';
                    if (filterType === 'week') ringColor = 'ring-violet-500';
                    if (filterType === 'interview_invitation') ringColor = 'ring-emerald-500';
                    
                    cardElement.classList.add('ring-2', ringColor);
                }
            }
            
            filterRows();
        }

        function resetDates() {
            document.getElementById('date-from-input').value = '';
            document.getElementById('date-to-input').value = '';
            filterRows();
        }

        function filterRows() {
            const hideSkipped = document.getElementById('hide-skipped-checkbox').checked;
            const onlyManual = document.getElementById('only-manual-checkbox').checked;
            const scoreFilter = document.getElementById('score-filter-select').value;
            const statusFilter = document.getElementById('status-filter-select').value;
            
            // Фильтр по датам
            const dateFromVal = document.getElementById('date-from-input').value;
            const dateToVal = document.getElementById('date-to-input').value;
            
            let dateFrom = null;
            let dateTo = null;
            if (dateFromVal) {
                dateFrom = new Date(dateFromVal);
                dateFrom.setHours(0, 0, 0, 0);
            }
            if (dateToVal) {
                dateTo = new Date(dateToVal);
                dateTo.setHours(23, 59, 59, 999);
            }

            const now = new Date();
            
            // Сегодняшняя дата без времени
            const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            
            // 7 дней назад
            const sevenDaysAgo = new Date();
            sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
            sevenDaysAgo.setHours(0, 0, 0, 0);

            const rows = document.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const isSkipped = row.getAttribute('data-is-skipped') === 'true';
                const isManual = row.getAttribute('data-is-manual') === 'true';
                const score = parseInt(row.querySelector('.col-score').getAttribute('data-score') || '0');
                const status = row.querySelector('.col-status select').value;
                const matchesSearch = row.getAttribute('data-matches-search') !== 'false';
                
                // Дата строки
                const dateText = row.querySelector('.col-date').innerText.trim();
                // Формат: YYYY-MM-DD HH:MM:SS -> преобразуем в Date
                const rowDate = new Date(dateText.replace(' ', 'T'));

                let show = true;
                
                if (!matchesSearch) show = false;
                if (hideSkipped && isSkipped) show = false;
                if (onlyManual && !isManual) show = false;
                
                // 1. Фильтр по оценке ИИ
                if (scoreFilter === 'high' && score < 7) show = false;
                if (scoreFilter === 'low' && score >= 7) show = false;
                
                // 2. Фильтр по статусу из выпадающего списка
                if (statusFilter !== 'all') {
                    if (statusFilter === 'applied' && !status.includes('Успешно')) show = false;
                    if (statusFilter === 'manual' && !status.includes('Требует ручной проверки')) show = false;
                    if (statusFilter === 'skipped' && !status.includes('Пропущено')) show = false;
                    if (statusFilter === 'error' && !status.includes('Ошибка')) show = false;
                }

                // 3. Интерактивный фильтр по клику на карточки
                if (currentCardFilter !== 'all') {
                    if (currentCardFilter === 'applied' && !status.includes('Успешно')) show = false;
                    if (currentCardFilter === 'manual' && !isManual) show = false;
                    if (currentCardFilter === 'skipped' && !isSkipped) show = false;
                    if (currentCardFilter === 'today' && rowDate < todayStart) show = false;
                    if (currentCardFilter === 'week' && rowDate < sevenDaysAgo) show = false;
                    if (currentCardFilter === 'interview_invitation') {
                        const selectEl = row.querySelector('.col-interview select');
                        if (selectEl && selectEl.value !== 'Приглашение') show = false;
                    }
                }

                // 4. Фильтр по периоду дат
                if (dateFrom && rowDate < dateFrom) show = false;
                if (dateTo && rowDate > dateTo) show = false;
                
                if (show) {
                    row.classList.remove('hidden');
                } else {
                    row.classList.add('hidden');
                }
            });
        }

        function liveSearch() {
            const query = document.getElementById('search-input').value.toLowerCase();
            const rows = document.querySelectorAll('tbody tr');
            
            rows.forEach(row => {
                const title = row.querySelector('.col-title').innerText.toLowerCase();
                const company = row.querySelector('.col-company').innerText.toLowerCase();
                const notesTextarea = row.querySelector('.col-notes textarea');
                const notes = notesTextarea ? notesTextarea.value.toLowerCase() : '';
                
                const matches = title.includes(query) || company.includes(query) || notes.includes(query);
                row.setAttribute('data-matches-search', matches ? 'true' : 'false');
            });
            filterRows();
        }

        let currentSort = { column: 'date', desc: true };

        function sortTable(column) {
            const table = document.querySelector('tbody');
            const rows = Array.from(table.querySelectorAll('tr'));
            
            let desc = true;
            if (currentSort.column === column) {
                desc = !currentSort.desc;
            }
            currentSort = { column, desc };

            // Обновляем стрелки сортировки
            document.querySelectorAll('.sort-arrow').forEach(arrow => arrow.innerText = '↕');
            const activeArrow = document.getElementById(`sort-arrow-${column}`);
            if (activeArrow) {
                activeArrow.innerText = desc ? '↓' : '↑';
            }

            rows.sort((a, b) => {
                let valA, valB;
                if (column === 'date') {
                    valA = a.querySelector('.col-date').innerText;
                    valB = b.querySelector('.col-date').innerText;
                    return desc ? valB.localeCompare(valA) : valA.localeCompare(valB);
                } else if (column === 'score') {
                    valA = parseInt(a.querySelector('.col-score').getAttribute('data-score') || '0');
                    valB = parseInt(b.querySelector('.col-score').getAttribute('data-score') || '0');
                    return desc ? valB - valA : valA - valB;
                } else if (column === 'title') {
                    valA = a.querySelector('.col-title').innerText;
                    valB = b.querySelector('.col-title').innerText;
                    return desc ? valB.localeCompare(valA) : valA.localeCompare(valB);
                }
                return 0;
            });

            rows.forEach(row => table.appendChild(row));
        }
        
        function showAI(reason, letter) {
            document.getElementById('modal-reason').innerText = reason || "Нет данных";
            document.getElementById('modal-letter').innerText = letter || "Нет письма";
            document.getElementById('modal').classList.remove('hidden');
            document.getElementById('modal').classList.add('flex');
        }
        
        function copyModalLetter() {
            const letterText = document.getElementById('modal-letter').innerText;
            if (!letterText || letterText === "Нет письма") return;
            
            navigator.clipboard.writeText(letterText).then(() => {
                const btn = document.getElementById('btn-copy-modal');
                const orig = btn.innerHTML;
                btn.innerHTML = '✓ Скопировано!';
                btn.classList.add('bg-green-600', 'text-white', 'border-green-500');
                btn.classList.remove('bg-slate-900', 'text-indigo-300', 'border-indigo-500/30');
                setTimeout(() => {
                    btn.innerHTML = orig;
                    btn.classList.remove('bg-green-600', 'text-white', 'border-green-500');
                    btn.classList.add('bg-slate-900', 'text-indigo-300', 'border-indigo-500/30');
                }, 1800);
            }).catch(() => alert('Не удалось скопировать'));
        }

        function hideModal() {
            document.getElementById('modal').classList.add('hidden');
            document.getElementById('modal').classList.remove('flex');
        }
    </script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen p-6 md:p-10 selection:bg-indigo-500 selection:text-white">
    <div class="max-w-[98%] mx-auto">
        <!-- Header -->
        <header class="flex flex-col md:flex-row items-start md:items-center justify-between mb-10 pb-6 border-b border-slate-900">
            <div>
                <div class="flex items-center space-x-3">
                    <span class="text-3xl">📊</span>
                    <h1 class="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">VibeClickerHH.ru Analyst</h1>
                </div>
                <p class="text-slate-400 text-sm mt-1">Интерактивный дашборд автооткликов и воронки собеседований</p>
            </div>
            <div class="mt-4 md:mt-0 flex flex-col sm:flex-row items-start sm:items-center gap-3">
                <div class="flex items-center space-x-2 bg-slate-900/50 border border-slate-800 px-3 py-2 rounded-xl text-xs text-slate-300">
                    <span class="text-indigo-400 text-sm">⏱️</span>
                    <span>Общее время работы бота: <strong class="text-indigo-300 font-bold">{{ total_duration_str }}</strong></span>
                </div>
                <div class="flex items-center space-x-3 bg-slate-900/50 border border-slate-800 px-3 py-2 rounded-xl text-xs text-slate-400">
                    <span class="w-2 h-2 bg-green-500 rounded-full animate-ping"></span>
                    <span>База данных подключена</span>
                </div>
            </div>
        </header>

        <!-- Stats & Funnel Section -->
        <div class="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-8">
            <!-- Left Side: Stats Cards (2/3 width) -->
            <div class="xl:col-span-2 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                <!-- Card 1 -->
                <div onclick="setCardFilter('all', this)" class="stats-card ring-2 ring-indigo-500 bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-indigo-500/50 cursor-pointer active:scale-[0.98]">
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Всего обработано</span>
                        <span class="p-1.5 bg-indigo-500/10 rounded-lg text-indigo-400 text-sm">📁</span>
                    </div>
                    <p class="text-3xl font-extrabold text-slate-100 mt-2">{{ total }}</p>
                </div>
                <!-- Card 2 -->
                <div onclick="setCardFilter('applied', this)" class="stats-card bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-green-500/50 cursor-pointer active:scale-[0.98]">
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Успешные отклики</span>
                        <span class="p-1.5 bg-green-500/10 rounded-lg text-green-400 text-sm">✅</span>
                    </div>
                    <p class="text-3xl font-extrabold text-green-400 mt-2">{{ applied }}</p>
                </div>
                <!-- Card 3 -->
                <div onclick="setCardFilter('manual', this)" class="stats-card bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-red-500/50 cursor-pointer active:scale-[0.98]">
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Требует проверки</span>
                        <span class="p-1.5 bg-red-500/10 rounded-lg text-red-400 text-sm">⚠️</span>
                    </div>
                    <p class="text-3xl font-extrabold text-red-500 mt-2">{{ manual_check }}</p>
                </div>
                <!-- Card 4 -->
                <div onclick="setCardFilter('skipped', this)" class="stats-card bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-yellow-500/50 cursor-pointer active:scale-[0.98]">
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Пропущено / Скип</span>
                        <span class="p-1.5 bg-yellow-500/10 rounded-lg text-yellow-400 text-sm">⏭️</span>
                    </div>
                    <p class="text-3xl font-extrabold text-slate-300 mt-2">{{ skipped }}</p>
                </div>
                <!-- Card 5 -->
                <div onclick="setCardFilter('interview_invitation', this)" class="stats-card bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:border-emerald-500/50 cursor-pointer active:scale-[0.98]">
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400 text-xs font-semibold uppercase tracking-wider">Приглашения</span>
                        <span class="p-1.5 bg-emerald-500/10 rounded-lg text-emerald-400 text-sm">✉️</span>
                    </div>
                    <p class="text-3xl font-extrabold text-emerald-400 mt-2">{{ invitations }}</p>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
            <!-- Left Side: Metric Cards (2/3 width) -->
            <div class="lg:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-4">
                <!-- Card 1: Всего попыток -->
                <div class="bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl flex flex-col justify-between">
                    <div class="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase tracking-wider mb-2">
                        <span>Всего в обработке</span>
                        <span class="text-slate-500 text-base">📊</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-slate-100">{{ total }}</div>
                    <div class="text-[11px] text-slate-500 mt-2 font-medium">Общее число просмотренных</div>
                </div>

                <!-- Card 2: Успешно отправлено -->
                <div class="bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl flex flex-col justify-between">
                    <div class="flex items-center justify-between text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-2">
                        <span>Отправлено откликов</span>
                        <span class="text-emerald-400 text-base">🚀</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-emerald-400">{{ applied }}</div>
                    <div class="text-[11px] text-slate-500 mt-2 font-medium">Успешно доставлено на hh.ru</div>
                </div>

                <!-- Card 3: Приглашения (Интервью) -->
                <div class="bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl flex flex-col justify-between">
                    <div class="flex items-center justify-between text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-2">
                        <span>Приглашения</span>
                        <span class="text-indigo-400 text-base">✉️</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-indigo-400">{{ invitations }}</div>
                    <div class="text-[11px] text-slate-500 mt-2 font-medium">Получено ответов от HR</div>
                </div>

                <!-- Card 4: Офферы -->
                <div class="bg-slate-900/60 backdrop-blur-md p-5 rounded-2xl border border-slate-900 shadow-xl flex flex-col justify-between">
                    <div class="flex items-center justify-between text-fuchsia-400 text-xs font-semibold uppercase tracking-wider mb-2">
                        <span>Получено Офферов</span>
                        <span class="text-fuchsia-400 text-base">🎉</span>
                    </div>
                    <div class="text-2xl sm:text-3xl font-extrabold text-fuchsia-400">{{ offers }}</div>
                    <div class="text-[11px] text-slate-500 mt-2 font-medium">Успешные офферы</div>
                </div>
            </div>
            
            <!-- Right Side: Conversion Funnel Widget (1/3 width) -->
            <div class="bg-slate-900/60 backdrop-blur-md p-6 rounded-2xl border border-slate-900 shadow-xl flex flex-col justify-between">
                <div>
                    <h3 class="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-4 flex items-center justify-between">
                        <span>📊 Воронка Конверсии</span>
                        <span class="text-[9px] font-bold bg-indigo-500/15 text-indigo-400 px-2 py-0.5 rounded-full uppercase tracking-wider">Live Analyst</span>
                    </h3>
                    
                    <div class="space-y-3.5">
                        <!-- Step 1: Успешные отклики -->
                        <div>
                            <div class="flex justify-between text-xs mb-1.5">
                                <span class="text-slate-400">Успешные отклики</span>
                                <span class="text-slate-200 font-bold">{{ applied }}</span>
                            </div>
                            <div class="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                                <div class="bg-gradient-to-r from-indigo-500 to-indigo-400 h-full rounded-full" style="width: 100%"></div>
                            </div>
                        </div>
                        
                        <!-- Step 2: Конверсия в приглашения -->
                        {% set conv_inv = ((invitations / applied * 100)|round(1)) if applied > 0 else 0 %}
                        <div>
                            <div class="flex justify-between text-xs mb-1.5">
                                <span class="text-slate-400 flex items-center space-x-1">
                                    <span>✉️ В приглашения</span>
                                </span>
                                <span class="text-emerald-400 font-bold">{{ conv_inv }}% <span class="text-[10px] text-slate-500 font-normal">({{ invitations }} шт)</span></span>
                            </div>
                            <div class="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                                <div class="bg-gradient-to-r from-emerald-500 to-emerald-400 h-full rounded-full" style="width: {{ conv_inv }}%"></div>
                            </div>
                        </div>

                        <!-- Step 3: Полученные офферы -->
                        {% set conv_off = ((offers / applied * 100)|round(1)) if applied > 0 else 0 %}
                        <div>
                            <div class="flex justify-between text-xs mb-1.5">
                                <span class="text-slate-400 flex items-center space-x-1">
                                    <span>🎉 В офферы</span>
                                </span>
                                <span class="text-fuchsia-400 font-bold">{{ conv_off }}% <span class="text-[10px] text-slate-500 font-normal">({{ offers }} шт)</span></span>
                            </div>
                            <div class="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                                <div class="bg-gradient-to-r from-fuchsia-500 to-fuchsia-400 h-full rounded-full" style="width: {{ conv_off }}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        
        <!-- Controls & Filters (Control Center) -->
        <section class="bg-slate-900/40 border border-slate-900 p-6 rounded-2xl mb-6 backdrop-blur-sm">
            <div class="flex flex-wrap gap-5 items-end">
                <!-- Search Box -->
                <div class="flex-grow min-w-[280px] max-w-md">
                    <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Живой поиск по таблице</label>
                    <div class="relative">
                        <input type="text" id="search-input" oninput="liveSearch()" placeholder="Поиск по названию вакансии, компании или заметкам..." class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all duration-200">
                        <span class="absolute right-3 top-3 text-slate-500">🔍</span>
                    </div>
                </div>
                <!-- Status Filter -->
                <div class="flex-grow sm:flex-none min-w-[190px]">
                    <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Фильтр по статусу отклика</label>
                    <select id="status-filter-select" onchange="filterRows()" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-all duration-200 cursor-pointer">
                        <option value="all">Все вакансии</option>
                        <option value="applied">Только успешные отклики</option>
                        <option value="manual">Только требующие ручной проверки</option>
                        <option value="skipped">Только пропущенные (Низкая оценка / Блэклист)</option>
                        <option value="error">Только ошибки</option>
                    </select>
                </div>
                <!-- Score Filter -->
                <div class="flex-grow sm:flex-none min-w-[190px]">
                    <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Фильтр по оценке соответствия</label>
                    <select id="score-filter-select" onchange="filterRows()" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-slate-300 focus:outline-none focus:border-indigo-500 transition-all duration-200 cursor-pointer">
                        <option value="all">Любая оценка</option>
                        <option value="high">Высокая оценка соответствия (>= 7)</option>
                        <option value="low">Низкая оценка соответствия (< 7)</option>
                    </select>
                </div>
                <!-- Date Filter Box -->
                <div class="flex-grow sm:flex-none min-w-[280px]">
                    <label class="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Фильтр по датам</label>
                    <div class="flex items-center space-x-1.5">
                        <input type="date" id="date-from-input" onchange="filterRows()" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all duration-200 cursor-pointer" title="Начальная дата">
                        <span class="text-slate-600 text-xs">—</span>
                        <input type="date" id="date-to-input" onchange="filterRows()" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-all duration-200 cursor-pointer" title="Конечная дата">
                        <button onclick="resetDates()" class="bg-slate-950 border border-slate-800 hover:bg-slate-800/80 p-2.5 rounded-xl text-xs text-slate-400 transition-all duration-200 cursor-pointer flex items-center justify-center font-bold" title="Сбросить даты">✕</button>
                    </div>
                </div>
                <!-- Quick Action Switches -->
                <div class="flex flex-col space-y-2 pb-1.5 min-w-[210px]">
                    <label class="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-slate-100 text-xs">
                        <input type="checkbox" id="hide-skipped-checkbox" onchange="filterRows()" class="form-checkbox h-4.5 w-4.5 bg-slate-950 border-slate-800 text-indigo-500 rounded focus:ring-0 focus:ring-offset-0">
                        <span class="font-medium">Скрыть пропущенные</span>
                    </label>
                    <label class="flex items-center space-x-2 cursor-pointer text-slate-300 hover:text-slate-100 text-xs">
                        <input type="checkbox" id="only-manual-checkbox" onchange="filterRows()" class="form-checkbox h-4.5 w-4.5 bg-slate-950 border-slate-800 text-red-500 rounded focus:ring-0 focus:ring-offset-0">
                        <span class="font-medium text-red-400">⚠️ Только требующие проверки</span>
                    </label>
                </div>
            </div>
        </section>

        <!-- Table Card -->
        <main class="bg-slate-900/30 border border-slate-900 rounded-2xl shadow-2xl overflow-hidden backdrop-blur-sm">
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-slate-900 text-left">
                    <thead class="bg-slate-900/80">
                        <tr>
                            <!-- Date Header -->
                            <th class="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:bg-slate-800/40 select-none group" onclick="sortTable('date')">
                                <div class="flex items-center space-x-1.5">
                                    <span>Дата</span>
                                    <span id="sort-arrow-date" class="sort-arrow text-[10px] text-indigo-400">↓</span>
                                </div>
                            </th>
                            <!-- Vacancy Header -->
                            <th class="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:bg-slate-800/40 select-none group" onclick="sortTable('title')">
                                <div class="flex items-center space-x-1.5">
                                    <span>Вакансия / Компания</span>
                                    <span id="sort-arrow-title" class="sort-arrow text-[10px] text-slate-500">↕</span>
                                </div>
                            </th>
                            <!-- Score Header -->
                            <th class="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider cursor-pointer hover:bg-slate-800/40 select-none group" onclick="sortTable('score')">
                                <div class="flex items-center space-x-1.5">
                                    <span>Оценка соответствия</span>
                                    <span id="sort-arrow-score" class="sort-arrow text-[10px] text-slate-500">↕</span>
                                </div>
                            </th>
                            <!-- Bot Status Header -->
                            <th class="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Статус бота</th>
                            <!-- Funnel Header -->
                            <th class="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Воронка (Собеседование)</th>
                            <!-- Notes Header -->
                            <th class="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider">Личные заметки</th>
                            <!-- Actions Header -->
                            <th class="px-6 py-4 text-xs font-bold text-slate-400 uppercase tracking-wider text-right">Детали / Действия</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-900/60 bg-slate-950/20">
                        {% for r in records %}
                        {% set is_skipped = 'true' if 'Пропущено' in (r.status or '') and 'Анкета/Тест' not in (r.status or '') else 'false' %}
                        {% set is_manual = 'true' if 'Требует ручной проверки' in (r.status or '') or 'Анкета/Те?ст' in (r.status or '') or 'Анкета/Тест' in (r.status or '') else 'false' %}
                        <tr data-is-skipped="{{ is_skipped }}" data-is-manual="{{ is_manual }}" data-matches-search="true" class="hover:bg-slate-900/45 transition-colors duration-150">
                            <!-- Date -->
                            <td class="col-date px-6 py-4 whitespace-nowrap text-xs text-slate-500 font-medium">
                                {{ r.timestamp.split('.')[0] }}
                            </td>
                            <!-- Vacancy Title & Company -->
                            <td class="px-6 py-4">
                                <div class="col-title font-semibold text-slate-200 text-sm hover:text-indigo-400 transition-colors duration-200">
                                    <a href="{{ r.url }}" target="_blank" class="flex items-center space-x-1.5">
                                        <span>{{ r.title or ('Вакансия ' ~ r.job_id) }}</span>
                                        <span class="text-xs text-slate-500">🔗</span>
                                    </a>
                                </div>
                                <div class="col-company text-xs text-slate-400 mt-0.5">{{ r.company }}</div>
                            </td>
                            <!-- Score -->
                            <td class="col-score px-6 py-4 whitespace-nowrap" data-score="{{ r.ai_score or 0 }}">
                                <span class="px-2.5 py-1 inline-flex text-xs leading-5 font-bold rounded-full 
                                    {% if r.ai_score and r.ai_score|int >= 7 %}bg-green-500/10 text-green-400 border border-green-500/20{% else %}bg-red-500/10 text-red-400 border border-red-500/20{% endif %}">
                                    {{ r.ai_score or '-' }} / 10
                                </span>
                            </td>
                            <!-- Bot Status -->
                            <td class="col-status px-6 py-4 whitespace-nowrap text-xs">
                                {% set status = r.status or '' %}
                                {% if 'Успешно' in status %}
                                    {% set status_color = 'bg-green-500/10 text-green-400 border border-green-500/30' %}
                                {% elif 'Низкая оценка' in status %}
                                    {% set status_color = 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/30' %}
                                {% elif 'Черный список' in status %}
                                    {% set status_color = 'bg-slate-500/10 text-slate-400 border border-slate-500/30' %}
                                {% else %}
                                    {% set status_color = 'bg-red-500/10 text-red-400 border border-red-500/30' %}
                                {% endif %}
                                <select onchange="updateBotStatus('{{ r.job_id }}', this)" class="font-semibold text-xs rounded-full px-2.5 py-1.5 transition-colors border {{ status_color }} cursor-pointer focus:outline-none">
                                    <option value="Успешно отправлено" class="bg-slate-950 text-slate-300" {% if status == 'Успешно отправлено' %}selected{% endif %}>Успешно отправлено</option>
                                    <option value="Требует ручной проверки" class="bg-slate-950 text-slate-300" {% if status == 'Требует ручной проверки' %}selected{% endif %}>⚠️ Требует проверки</option>
                                    <option value="Ошибка (вмешательство пользователя)" class="bg-slate-950 text-slate-300" {% if status == 'Ошибка (вмешательство пользователя)' %}selected{% endif %}>Ошибка (ручное вмешательство)</option>
                                    <option value="Пропущено (Низкая оценка ИИ)" class="bg-slate-950 text-slate-300" {% if status == 'Пропущено (Низкая оценка ИИ)' %}selected{% endif %}>Пропущено (Низкая оценка)</option>
                                    <option value="Пропущено (Черный список)" class="bg-slate-950 text-slate-300" {% if status == 'Пропущено (Черный список)' %}selected{% endif %}>Пропущено (Черный список)</option>
                                    <option value="Пропущено (Анкета/Тест)" class="bg-slate-950 text-slate-300" {% if status == 'Пропущено (Анкета/Тест)' %}selected{% endif %}>Пропущено (Анкета/Тест)</option>
                                    <option value="Пропущено (Кнопка не найдена)" class="bg-slate-950 text-slate-300" {% if status == 'Пропущено (Кнопка не найдена)' %}selected{% endif %}>Пропущено (Кнопка не найдена)</option>
                                    <option value="Ошибка: не вставилось письмо" class="bg-slate-950 text-slate-300" {% if status == 'Ошибка: не вставилось письмо' %}selected{% endif %}>Ошибка: не вставилось письмо</option>
                                    <option value="Успешно (Тестовый режим)" class="bg-slate-950 text-slate-300" {% if status == 'Успешно (Тестовый режим)' %}selected{% endif %}>Успешно (Тестовый режим)</option>
                                </select>
                            </td>
                            <!-- Funnel (Interview) -->
                            <td class="col-interview px-6 py-4 whitespace-nowrap">
                                <select onchange="updateStatus('{{ r.job_id }}', this)" class="block w-full pl-3 pr-8 py-1.5 text-xs bg-slate-950 border-slate-800 text-slate-300 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 rounded-lg transition-colors border cursor-pointer">
                                    <option value="Ожидание" {% if r.interview_status == 'Ожидание' %}selected{% endif %}>Ожидание ответа</option>
                                    <option value="Приглашение" {% if r.interview_status == 'Приглашение' %}selected{% endif %}>✅ Приглашение</option>
                                    <option value="Тестовое" {% if r.interview_status == 'Тестовое' %}selected{% endif %}>📝 Получил тестовое</option>
                                    <option value="Отказ" {% if r.interview_status == 'Отказ' %}selected{% endif %}>❌ Отказ</option>
                                    <option value="Оффер" {% if r.interview_status == 'Оффер' %}selected{% endif %}>🎉 ПОЛУЧИЛ ОФФЕР!</option>
                                </select>
                            </td>
                            <!-- User Notes -->
                            <td class="col-notes px-6 py-4 min-w-[200px] max-w-[300px]">
                                <!-- Режим просмотра -->
                                <div id="view-notes-{{ r.job_id }}" onclick="enableNotesEdit('{{ r.job_id }}')" class="group cursor-pointer p-2.5 rounded-xl border border-slate-900/40 hover:border-slate-800/80 hover:bg-slate-900/40 transition-all duration-200">
                                    {% if r.user_notes %}
                                        <p id="text-notes-{{ r.job_id }}" class="text-xs text-slate-300 break-words leading-relaxed line-clamp-3 group-hover:text-indigo-300 transition-colors">{{ r.user_notes }}</p>
                                        <span class="text-[10px] text-slate-500 mt-1 opacity-0 group-hover:opacity-100 transition-opacity flex items-center space-x-1">
                                            <span>✏️ Кликните для изменения</span>
                                        </span>
                                    {% else %}
                                        <span class="inline-flex items-center space-x-1.5 text-xs text-slate-500 group-hover:text-indigo-400 font-medium transition-colors">
                                            <span>➕</span>
                                            <span>Добавить заметку</span>
                                        </span>
                                    {% endif %}
                                </div>

                                <!-- Режим редактирования (скрыт по умолчанию) -->
                                <div id="edit-notes-{{ r.job_id }}" class="hidden flex-col space-y-2 mt-1">
                                    <textarea id="textarea-notes-{{ r.job_id }}" rows="2" class="w-full text-xs bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 focus:shadow-[0_0_10px_rgba(129,140,248,0.15)] text-slate-200 rounded-xl p-2.5 transition-all duration-200 resize-y" placeholder="Введите заметку...">{{ r.user_notes or '' }}</textarea>
                                    <div class="flex items-center justify-between text-[11px]">
                                        <span id="status-notes-{{ r.job_id }}" class="text-green-400 font-medium opacity-0 transition-opacity duration-300">Сохранено ✓</span>
                                        <div class="flex items-center space-x-1.5 ml-auto">
                                            <button onclick="cancelNotesEdit('{{ r.job_id }}')" class="px-2.5 py-1 bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition-colors">Отмена</button>
                                            <button onclick="saveInlineNotes('{{ r.job_id }}')" class="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-semibold shadow-md hover:shadow-indigo-600/20 transition-all duration-200">Сохранить</button>
                                        </div>
                                    </div>
                                </div>
                            </td>
                            <!-- Actions & Modal Button -->
                            <td class="px-6 py-4 whitespace-nowrap text-right text-xs font-semibold space-x-2">
                                <button onclick="showAI({{ r.ai_reason | tojson | forceescape }}, {{ r.cover_letter | tojson | forceescape }})" class="inline-flex items-center text-indigo-400 hover:text-indigo-200 bg-indigo-500/10 hover:bg-indigo-500/20 px-3 py-1.5 rounded-lg border border-indigo-500/20 transition-all duration-200 cursor-pointer">📖 Анализ & Письмо</button>
                                <button onclick="deleteRow('{{ r.job_id }}', this)" class="inline-flex items-center text-red-400 hover:text-red-200 bg-red-500/10 hover:bg-red-500/20 px-3 py-1.5 rounded-lg border border-red-500/20 transition-all duration-200 cursor-pointer">🗑️ Удалить</button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </main>
    </div>

    <!-- Details Premium Modal -->
    <div id="modal" class="hidden fixed inset-0 bg-slate-950/80 backdrop-blur-md items-center justify-center p-4 z-50 transition-opacity duration-300">
        <div class="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full p-6 max-h-[85vh] overflow-y-auto shadow-2xl flex flex-col">
            <header class="flex items-center justify-between pb-4 border-b border-slate-800 mb-5">
                <h2 class="text-xl font-bold bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent flex items-center space-x-2">
                    <span>📊</span>
                    <span>Детальный анализ вакансии</span>
                </h2>
                <button onclick="hideModal()" class="text-slate-400 hover:text-slate-100 text-lg bg-slate-850 p-1.5 rounded-xl border border-slate-800 hover:bg-slate-800 transition-colors">✕</button>
            </header>
            
            <div class="flex-grow space-y-6">
                <!-- AI Reason Section -->
                <div>
                    <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2.5">Резюме оценки ИИ</h3>
                    <p id="modal-reason" class="text-slate-200 text-sm leading-relaxed bg-slate-950 p-4 rounded-2xl border border-slate-800 italic"></p>
                </div>
                
                <!-- Cover Letter Section -->
                <div>
                    <h3 class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2.5">Сгенерированное сопроводительное письмо</h3>
                    <pre id="modal-letter" class="whitespace-pre-wrap text-xs text-slate-200 bg-slate-950 p-4 rounded-2xl border border-slate-800 leading-relaxed font-mono"></pre>
                </div>
            </div>
            
            <footer class="mt-6 pt-4 border-t border-slate-800 flex justify-between items-center">
                <button id="btn-copy-modal" onclick="copyModalLetter()" class="bg-slate-900 hover:bg-slate-800 text-indigo-300 border border-indigo-500/30 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 cursor-pointer flex items-center space-x-2">📋 Скопировать письмо</button>
                <button onclick="hideModal()" class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 cursor-pointer shadow-lg hover:shadow-indigo-600/30">Закрыть</button>
            </footer>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    import datetime
    records = Database.get_all_records()
    total = len(records)
    applied = sum(1 for r in records if r.get("status") and "Успешно" in r.get("status"))
    manual_check = sum(1 for r in records if r.get("status") and (("Требует ручной проверки" in r.get("status")) or ("Анкета/Тест" in r.get("status"))))
    skipped = total - applied - manual_check
    
    # Расчет общего времени работы бота
    total_seconds = Database.get_total_duration()
    if total_seconds == 0:
        total_duration_str = "0 сек"
    else:
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        
        parts = []
        if h > 0:
            parts.append(f"{h} ч")
        if m > 0:
            parts.append(f"{m} мин")
        if s > 0 or not parts:
            parts.append(f"{s} сек")
        total_duration_str = " ".join(parts)

    # Новые метрики для аналитики конверсии
    invitations = sum(1 for r in records if r.get("interview_status") == "Приглашение")
    test_tasks = sum(1 for r in records if r.get("interview_status") == "Тестовое")
    offers = sum(1 for r in records if r.get("interview_status") == "Оффер")
    
    # Расчет статистики по датам
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    applied_today = sum(1 for r in records if r.get("timestamp") and r.get("timestamp").startswith(today_str) and "Успешно" in r.get("status"))
    total_today = sum(1 for r in records if r.get("timestamp") and r.get("timestamp").startswith(today_str))
    
    one_week_ago = now - datetime.timedelta(days=7)
    applied_week = 0
    total_week = 0
    for r in records:
        if r.get("timestamp"):
            try:
                dt_str = r.get("timestamp").split('.')[0]
                dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                if dt >= one_week_ago:
                    total_week += 1
                    if r.get("status") and "Успешно" in r.get("status"):
                        applied_week += 1
            except Exception:
                pass
                
    return render_template_string(
        HTML_TEMPLATE, 
        records=records, 
        total=total, 
        applied=applied, 
        manual_check=manual_check, 
        skipped=skipped,
        invitations=invitations,
        test_tasks=test_tasks,
        offers=offers,
        applied_today=applied_today,
        total_today=total_today,
        applied_week=applied_week,
        total_week=total_week,
        total_duration_str=total_duration_str
    )

@app.route('/api/update_status', methods=['POST'])
def update_status():
    data = request.json
    Database.update_interview_status(data['job_id'], data['status'])
    return jsonify({"success": True})

@app.route('/api/update_bot_status', methods=['POST'])
def update_bot_status():
    data = request.json
    Database.update_bot_status(data['job_id'], data['status'])
    return jsonify({"success": True})

@app.route('/api/update_notes', methods=['POST'])
def update_notes():
    data = request.json
    Database.update_user_notes(data['job_id'], data['notes'])
    return jsonify({"success": True})

@app.route('/api/delete_vacancy', methods=['POST'])
def delete_vacancy():
    data = request.json
    Database.delete_vacancy(data['job_id'])
    return jsonify({"success": True})

if __name__ == '__main__':
    print("=========================================================")
    print("Zapusk interaktivnogo dashborda na http://localhost:5000")
    print("=========================================================")
    app.run(debug=True, port=5000, use_reloader=False)
