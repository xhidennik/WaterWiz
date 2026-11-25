/**
 * Задачи на день: генерация из data-task.js, хранение в localStorage, вывод списка.
 */

(function () {
    function loadAllTasks() {
        try {
            var raw = localStorage.getItem(TASK_STORAGE_KEY);
            if (raw) return JSON.parse(raw);
        } catch (e) {}
        return [];
    }

    function saveAllTasks(tasks) {
        localStorage.setItem(TASK_STORAGE_KEY, JSON.stringify(tasks));
    }

    function randomItem(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    function randomInt(min, max) {
        return min + Math.floor(Math.random() * (max - min + 1));
    }

    function id() {
        return 't' + Date.now() + '-' + Math.random().toString(36).slice(2, 9);
    }

    function ensureTasksForMonth(year, month) {
        var all = loadAllTasks();
        var prefix = year + '-' + (month < 10 ? '0' + month : String(month));
        var hasAny = all.some(function (t) { return t.date && t.date.indexOf(prefix) === 0; });
        if (hasAny) return;

        var daysInMonth = new Date(year, month, 0).getDate();
        for (var day = 1; day <= daysInMonth; day++) {
            var dateStr = prefix + '-' + (day < 10 ? '0' + day : String(day));
            var count = randomInt(0, 4);
            for (var i = 0; i < count; i++) {
                var status = randomItem(TASK_STATUSES);
                var template = randomItem(TASK_TEMPLATES);
                all.push({
                    id: id(),
                    date: dateStr,
                    title: template.title,
                    place: randomItem(TASK_PLACES),
                    description: template.description,
                    responsible: randomItem(RESPONSIBLE_PEOPLE),
                    status: status.id
                });
            }
        }
        saveAllTasks(all);
    }

    function getTasksForDay(dateStr) {
        return loadAllTasks().filter(function (t) { return t.date === dateStr; });
    }

    function getStatusById(statusId) {
        for (var i = 0; i < TASK_STATUSES.length; i++) {
            if (TASK_STATUSES[i].id === statusId) return TASK_STATUSES[i];
        }
        return TASK_STATUSES[0];
    }

    function formatDateLabel(dateStr) {
        var parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        var months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        var m = parseInt(parts[1], 10);
        return parseInt(parts[2], 10) + ' ' + (months[m - 1] || '') + ' ' + parts[0];
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderTaskList(dateStr, containerEl, titleEl) {
        if (!containerEl) return;
        if (titleEl) titleEl.textContent = 'Задачи на ' + formatDateLabel(dateStr);

        ensureTasksForMonth(
            parseInt(dateStr.slice(0, 4), 10),
            parseInt(dateStr.slice(5, 7), 10)
        );

        var tasks = getTasksForDay(dateStr);
        containerEl.innerHTML = '';

        if (tasks.length === 0) {
            containerEl.innerHTML = '<p class="tasks-empty">На этот день задач нет.</p>';
            return;
        }

        tasks.forEach(function (task) {
            var st = getStatusById(task.status);
            var card = document.createElement('div');
            card.className = 'task-card';
            card.innerHTML =
                '<div class="task-card__header">' +
                '<span class="task-card__title">' + escapeHtml(task.title) + '</span>' +
                '<span class="task-card__status task-card__status--' + escapeHtml(st.class) + '">' + escapeHtml(st.label) + '</span>' +
                '</div>' +
                '<div class="task-card__meta">' +
                '<span class="task-card__place"><i class="fas fa-map-marker-alt"></i> ' + escapeHtml(task.place) + '</span>' +
                '<span class="task-card__responsible"><i class="fas fa-user"></i> ' + escapeHtml(task.responsible) + '</span>' +
                '</div>' +
                (task.description ? '<p class="task-card__desc">' + escapeHtml(task.description) + '</p>' : '');
            containerEl.appendChild(card);
        });
    }

    function initTasks() {
        var tasksWrap = document.getElementById('tasksList');
        var tasksTitle = document.getElementById('tasksDayTitle');
        if (!tasksWrap) return;

        window.WaterWizCalendar.init(function (dateStr) {
            renderTaskList(dateStr, tasksWrap, tasksTitle);
        });

        var my = window.WaterWizCalendar.getCurrentMonthYear();
        if (my) ensureTasksForMonth(my.year, my.month);

        var today = new Date();
        var todayStr = today.getFullYear() + '-' + (today.getMonth() + 1 < 10 ? '0' : '') + (today.getMonth() + 1) + '-' + (today.getDate() < 10 ? '0' : '') + today.getDate();
        var firstDayOfMonth = my.year + '-' + (my.month < 10 ? '0' + my.month : String(my.month)) + '-01';
        var lastDay = new Date(my.year, my.month, 0).getDate();
        var lastDayStr = my.year + '-' + (my.month < 10 ? '0' + my.month : String(my.month)) + '-' + (lastDay < 10 ? '0' : '') + lastDay;
        var dateToShow = (todayStr >= firstDayOfMonth && todayStr <= lastDayStr) ? todayStr : firstDayOfMonth;
        window.WaterWizCalendar.setSelectedDate(dateToShow);
        renderTaskList(dateToShow, tasksWrap, tasksTitle);

        var monthEl = document.getElementById('calendarMonth');
        var yearEl = document.getElementById('calendarYear');
        function onMonthYearChange() {
            setTimeout(function () {
                var my2 = window.WaterWizCalendar.getCurrentMonthYear();
                if (!my2) return;
                ensureTasksForMonth(my2.year, my2.month);
                var first = my2.year + '-' + (my2.month < 10 ? '0' : '') + my2.month + '-01';
                window.WaterWizCalendar.setSelectedDate(first);
                renderTaskList(first, tasksWrap, tasksTitle);
            }, 0);
        }
        if (monthEl) monthEl.addEventListener('change', onMonthYearChange);
        if (yearEl) yearEl.addEventListener('change', onMonthYearChange);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTasks);
    } else {
        initTasks();
    }
})();
