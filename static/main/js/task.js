/**
 * Water tracker: календарь + to-do лист.
 * Задачи хранятся в БД (API), генератор использует data-task.js шаблоны.
 */

(function () {
    function randomItem(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    function randomInt(min, max) {
        return min + Math.floor(Math.random() * (max - min + 1));
    }

    function pad(n) {
        return n < 10 ? '0' + n : String(n);
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function formatDateLabel(dateStr) {
        var parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        var months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        var m = parseInt(parts[1], 10);
        return parseInt(parts[2], 10) + ' ' + (months[m - 1] || '') + ' ' + parts[0];
    }

    function getStatusById(statusId) {
        for (var i = 0; i < TASK_STATUSES.length; i++) {
            if (TASK_STATUSES[i].id === statusId) return TASK_STATUSES[i];
        }
        return TASK_STATUSES[0];
    }

    function getPriorityById(priorityId) {
        for (var i = 0; i < TASK_PRIORITIES.length; i++) {
            if (TASK_PRIORITIES[i].id === priorityId) return TASK_PRIORITIES[i];
        }
        return TASK_PRIORITIES[0];
    }

    function getCsrfToken() {
        var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return el ? el.value : '';
    }

    const apiBase = '/api';

    async function apiFetchJson(url, options) {
        const res = await fetch(url, options);
        if (!res.ok) {
            const txt = await res.text().catch(function () { return ''; });
            throw new Error(txt || ('HTTP ' + res.status));
        }
        return res.json();
    }

    function openModal(modalEl, overlayEl) {
        if (overlayEl) overlayEl.classList.add('active');
        if (modalEl) modalEl.classList.add('active');
    }

    function closeModal(modalEl, overlayEl) {
        if (overlayEl) overlayEl.classList.remove('active');
        if (modalEl) modalEl.classList.remove('active');
    }

    function dateStrFromDate(d) {
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    }

    function withinInclusiveRandomDate(startDate, endDate) {
        const msStart = startDate.getTime();
        const msEnd = endDate.getTime();
        const diffDays = Math.floor((msEnd - msStart) / (24 * 3600 * 1000));
        const addDays = randomInt(0, diffDays);
        const result = new Date(msStart + addDays * 24 * 3600 * 1000);
        return result;
    }

    function initWarehouseTabs() {
        const tabs = document.querySelectorAll('.warehouse-tab');
        const contents = document.querySelectorAll('.warehouse-content');
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                const tabId = tab.getAttribute('data-tab');
                tabs.forEach(function (t) { t.classList.remove('active'); });
                contents.forEach(function (c) {
                    c.classList.remove('active');
                    if (c.id === tabId) c.classList.add('active');
                });
                tab.classList.add('active');
            });
        });
    }

    function wireTasksPage() {
        const tasksWrap = document.getElementById('tasksList');
        const tasksTitle = document.getElementById('tasksDayTitle');
        const tasksApiError = document.getElementById('tasksApiError');
        const locationFilter = document.getElementById('locationFilter');

        const locationsList = document.getElementById('locationsList');

        const overlayEl = document.getElementById('taskModalOverlay');
        const modalEl = document.getElementById('taskModal');

        const taskForm = document.getElementById('taskForm');
        const taskIdEl = document.getElementById('taskId');

        const taskModalTitle = document.getElementById('taskModalTitle');
        const taskTitleEl = document.getElementById('taskTitle');
        const taskDescriptionEl = document.getElementById('taskDescription');
        const taskLocationEl = document.getElementById('taskLocation');
        const taskExecutorEl = document.getElementById('taskExecutor');
        const taskDateEl = document.getElementById('taskDate');
        const taskDurationDaysEl = document.getElementById('taskDurationDays');
        const taskStatusEl = document.getElementById('taskStatus');
        const taskPriorityEl = document.getElementById('taskPriority');
        const taskCancelBtn = document.getElementById('taskCancelBtn');
        const taskFormError = document.getElementById('taskFormError');

        const createTaskBtn = document.getElementById('createTaskBtn');
        const generateTasksBtn = document.getElementById('generateTasksBtn');
        const genCountEl = document.getElementById('genCount');

        if (!tasksWrap || !tasksTitle) return;

        const csrfToken = getCsrfToken();

        let selectedDate = null;
        let selectedLocationId = '';
        let locations = [];
        let users = [];

        function showTasksError(msg) {
            if (!tasksApiError) return;
            tasksApiError.textContent = msg || '';
            tasksApiError.style.display = msg ? 'block' : 'none';
        }

        function renderLocations() {
            if (!locationsList) return;
            if (!locations || locations.length === 0) {
                locationsList.innerHTML = '<p class="tasks-empty">Локаций нет.</p>';
                return;
            }
            locationsList.innerHTML = locations.map(function (l) {
                return '<div class="location-pill"><div style="font-weight:700;color:var(--dark);">' +
                    escapeHtml(l.name) + '</div></div>';
            }).join('');
        }

        function populateLocationSelects() {
            if (locationFilter) {
                const current = locationFilter.value || '';
                locationFilter.innerHTML = '<option value="">Все локации</option>' +
                    locations.map(function (l) {
                        const selected = l.id == current ? ' selected' : '';
                        return '<option value="' + l.id + '"' + selected + '>' + escapeHtml(l.name) + '</option>';
                    }).join('');
            }

            if (taskLocationEl) {
                taskLocationEl.innerHTML = locations.map(function (l) {
                    return '<option value="' + l.id + '">' + escapeHtml(l.name) + '</option>';
                }).join('');
            }
        }

        function populateExecutorSelect() {
            if (!taskExecutorEl) return;
            const current = taskExecutorEl.value || '';
            taskExecutorEl.innerHTML = users.map(function (u) {
                const selected = u.id == current ? ' selected' : '';
                const staffMark = u.is_staff ? ' (сотрудник)' : '';
                return '<option value="' + u.id + '"' + selected + '>' + escapeHtml(u.display_name) + staffMark + '</option>';
            }).join('');
        }

        async function loadLocations() {
            const data = await apiFetchJson(apiBase + '/locations/', { method: 'GET', credentials: 'same-origin' });
            locations = data.locations || [];
            renderLocations();
            populateLocationSelects();
        }

        async function loadUsers() {
            const data = await apiFetchJson(apiBase + '/users/', { method: 'GET', credentials: 'same-origin' });
            users = data.users || [];
            populateExecutorSelect();
        }

        function collectTaskFromModal() {
            return {
                title: taskTitleEl ? (taskTitleEl.value || '').trim() : '',
                description: taskDescriptionEl ? (taskDescriptionEl.value || '').trim() : '',
                location_id: taskLocationEl ? taskLocationEl.value : '',
                executor_id: taskExecutorEl ? taskExecutorEl.value : '',
                date: taskDateEl ? taskDateEl.value : '',
                duration_days: parseInt(taskDurationDaysEl ? taskDurationDaysEl.value : '1', 10),
                status: taskStatusEl ? taskStatusEl.value : 'pending',
                priority: taskPriorityEl ? taskPriorityEl.value : 'low',
            };
        }

        function setModalValuesForCreate(dateStr) {
            if (taskIdEl) taskIdEl.value = '';
            if (taskModalTitle) taskModalTitle.textContent = 'Новая задача';
            if (taskTitleEl) taskTitleEl.value = '';
            if (taskDescriptionEl) taskDescriptionEl.value = '';
            if (taskDateEl) taskDateEl.value = dateStr || '';
            if (taskDurationDaysEl) taskDurationDaysEl.value = 1;
            if (taskStatusEl) taskStatusEl.value = 'pending';
            if (taskPriorityEl) taskPriorityEl.value = 'low';
            if (taskLocationEl) {
                if (selectedLocationId) taskLocationEl.value = selectedLocationId;
                else if (locations && locations.length > 0) taskLocationEl.value = locations[0].id;
            }
            if (taskExecutorEl) {
                if (users && users.length > 0) taskExecutorEl.value = users[0].id;
            }
        }

        function hideTaskFormError() {
            if (!taskFormError) return;
            taskFormError.textContent = '';
            taskFormError.style.display = 'none';
        }

        function showTaskFormError(msg) {
            if (!taskFormError) return;
            taskFormError.textContent = msg || '';
            taskFormError.style.display = 'block';
        }

        async function apiGetTasksForDay(dateStr) {
            let url = apiBase + '/tasks/?date=' + encodeURIComponent(dateStr);
            if (selectedLocationId) url += '&location_id=' + encodeURIComponent(selectedLocationId);
            const data = await apiFetchJson(url, { method: 'GET', credentials: 'same-origin' });
            return data.tasks || [];
        }

        function renderTaskList(tasks) {
            tasksWrap.innerHTML = '';
            if (!tasks || tasks.length === 0) {
                tasksWrap.innerHTML = '<p class="tasks-empty">На этот день задач нет.</p>';
                return;
            }

            tasks.forEach(function (t) {
                const st = getStatusById(t.status);
                const pr = getPriorityById(t.priority);
                const card = document.createElement('div');
                card.className = 'task-card task-card--priority-' + escapeHtml(pr.id);

                const due = t.deadline_date ? ('Дедлайн: ' + formatDateLabel(t.deadline_date)) : '';
                card.innerHTML =
                    '<div class="task-card__header">' +
                    '<span class="task-card__title">' + escapeHtml(t.title) + '</span>' +
                    '<span class="task-card__status task-card__status--' + escapeHtml(st.class) + '">' + escapeHtml(st.label) + '</span>' +
                    '</div>' +
                    '<div class="task-card__meta">' +
                    '<span class="task-card__place"><i class="fas fa-map-marker-alt"></i> ' + escapeHtml(t.location && t.location.name ? t.location.name : '') + '</span>' +
                    '<span class="task-card__responsible"><i class="fas fa-user"></i> ' + escapeHtml(t.executor || '') + '</span>' +
                    '<span class="task-card__priority task-card__priority--' + escapeHtml(pr.class) + '"><i class="fas fa-flag"></i> ' + escapeHtml(pr.label) + '</span>' +
                    '</div>' +
                    (t.description ? '<p class="task-card__desc" style="margin: 10px 0 0; color: var(--gray);">' + escapeHtml(t.description) + '</p>' : '') +
                    (due ? '<p style="margin: 10px 0 0; font-size: 13px; color: var(--dark);"><i class="far fa-clock"></i> ' + escapeHtml(due) + '</p>' : '') +
                    '<div style="display:flex; gap: 10px; margin-top: 12px; flex-wrap: wrap;">' +
                    '  <button type="button" class="btn btn-sm btn-info task-edit-btn" data-task-id="' + t.id + '"><i class="fas fa-edit"></i> Изменить</button>' +
                    '  <button type="button" class="btn btn-sm btn-success task-delete-btn" data-task-id="' + t.id + '"><i class="fas fa-trash"></i> Удалить</button>' +
                    '</div>';

                tasksWrap.appendChild(card);
            });
        }

        async function refreshTasks() {
            if (!selectedDate) return;
            showTasksError('');
            try {
                const tasks = await apiGetTasksForDay(selectedDate);
                renderTaskList(tasks);
            } catch (e) {
                showTasksError('Не удалось загрузить задачи: ' + (e && e.message ? e.message : 'ошибка'));
            }
        }

        async function fillModalFromTaskId(taskId) {
            const tasks = await apiGetTasksForDay(selectedDate);
            for (var i = 0; i < tasks.length; i++) {
                if (String(tasks[i].id) === String(taskId)) {
                    const t = tasks[i];
                    if (taskIdEl) taskIdEl.value = t.id;
                    if (taskModalTitle) taskModalTitle.textContent = 'Редактирование задачи';
                    if (taskTitleEl) taskTitleEl.value = t.title || '';
                    if (taskDescriptionEl) taskDescriptionEl.value = t.description || '';
                    if (taskDateEl) taskDateEl.value = t.date || '';
                    if (taskDurationDaysEl) taskDurationDaysEl.value = t.duration_days || 1;
                    if (taskStatusEl) taskStatusEl.value = t.status || 'pending';
                    if (taskPriorityEl) taskPriorityEl.value = t.priority || 'low';
                    if (taskLocationEl) taskLocationEl.value = t.location && t.location.id ? t.location.id : '';
                    if (taskExecutorEl) taskExecutorEl.value = t.executor_id || '';
                    return true;
                }
            }
            return false;
        }

        createTaskBtn && createTaskBtn.addEventListener('click', function () {
            hideTaskFormError();
            setModalValuesForCreate(selectedDate || '');
            openModal(modalEl, overlayEl);
        });

        taskCancelBtn && taskCancelBtn.addEventListener('click', function () {
            hideTaskFormError();
            closeModal(modalEl, overlayEl);
        });

        overlayEl && overlayEl.addEventListener('click', function () {
            hideTaskFormError();
            closeModal(modalEl, overlayEl);
        });

        taskForm && taskForm.addEventListener('submit', function (e) {
            e.preventDefault();
            hideTaskFormError();

            const payload = collectTaskFromModal();
            if (!payload.title || !payload.date || !payload.location_id) {
                showTaskFormError('Проверьте поля: название, дата и локация обязательны.');
                return;
            }

            const isEdit = !!taskIdEl.value;

            (async function () {
                try {
                    if (!isEdit) {
                        await apiFetchJson(apiBase + '/tasks/', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken
                            },
                            body: JSON.stringify(payload)
                        });
                    } else {
                        await apiFetchJson(apiBase + '/tasks/' + taskIdEl.value + '/', {
                            method: 'PUT',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken
                            },
                            body: JSON.stringify(payload)
                        });
                    }
                    closeModal(modalEl, overlayEl);
                    await refreshTasks();
                } catch (err) {
                    showTaskFormError((err && err.message) ? err.message : 'Ошибка сохранения');
                }
            })();
        });

        tasksWrap && tasksWrap.addEventListener('click', function (e) {
            const target = e.target;
            if (!target) return;

            const editBtn = target.closest && target.closest('.task-edit-btn');
            if (editBtn) {
                const taskId = editBtn.getAttribute('data-task-id');
                (async function () {
                    const ok = await fillModalFromTaskId(taskId);
                    if (!ok) showTasksError('Не удалось загрузить задачу для редактирования.');
                    else openModal(modalEl, overlayEl);
                })();
                return;
            }

            const deleteBtn = target.closest && target.closest('.task-delete-btn');
            if (deleteBtn) {
                const taskId = deleteBtn.getAttribute('data-task-id');
                const ok = confirm('Удалить задачу №' + taskId + '?');
                if (!ok) return;
                (async function () {
                    try {
                        await apiFetchJson(apiBase + '/tasks/' + taskId + '/', {
                            method: 'DELETE',
                            credentials: 'same-origin',
                            headers: { 'X-CSRFToken': csrfToken }
                        });
                        await refreshTasks();
                    } catch (err) {
                        showTasksError('Не удалось удалить задачу.');
                    }
                })();
            }
        });

        function generateTasksClientSide(count, monthYear, locationsArr) {
            const year = monthYear.year;
            const month = monthYear.month; // 1..12

            const now = new Date();
            const monthStart = new Date(year, month - 1, 1);
            const monthEnd = new Date(year, month, 0);
            const maxEnd = new Date(Math.min(monthEnd.getTime(), now.getTime()));
            if (maxEnd < monthStart) {
                return [];
            }

            const result = [];
            for (let i = 0; i < count; i++) {
                const template = randomItem(TASK_TEMPLATES);
                const status = randomItem(TASK_STATUSES);
                const priority = randomItem(TASK_PRIORITIES);

                const loc = locationsArr && locationsArr.length ? randomItem(locationsArr) : null;
                if (!loc) continue;

                const randomDate = withinInclusiveRandomDate(monthStart, maxEnd);
                result.push({
                    title: template.title,
                    description: template.description,
                    location_id: loc.id,
                    date: dateStrFromDate(randomDate),
                    duration_days: randomInt(1, 7),
                    status: status.id,
                    priority: priority.id,
                });
            }
            return result;
        }

        generateTasksBtn && generateTasksBtn.addEventListener('click', function () {
            if (!locations || locations.length === 0) {
                showTasksError('Сначала загрузите локации.');
                return;
            }

            const count = parseInt(genCountEl && genCountEl.value ? genCountEl.value : '20', 10);
            if (!count || count < 1) return;

            const my = window.WaterWizCalendar.getCurrentMonthYear();
            if (!my) return;

            (async function () {
                try {
                    showTasksError('');
                    const generated = generateTasksClientSide(count, my, locations);
                    if (!generated.length) {
                        renderTaskList([]);
                        return;
                    }

                    await apiFetchJson(apiBase + '/tasks/', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({ tasks: generated })
                    });

                    await refreshTasks();
                } catch (err) {
                    showTasksError('Не удалось сгенерировать задачи.');
                }
            })();
        });

        // Calendar wiring
        window.WaterWizCalendar.init(function (dateStr) {
            selectedDate = dateStr;
            if (tasksTitle) tasksTitle.textContent = 'Задачи на ' + formatDateLabel(dateStr);
            refreshTasks();
        });

        // При смене месяца/года показываем подходящую дату (обычно "сегодня" или 1-е число)
        const monthEl = document.getElementById('calendarMonth');
        const yearEl = document.getElementById('calendarYear');
        function onMonthYearChange() {
            setTimeout(function () {
                const my2 = window.WaterWizCalendar.getCurrentMonthYear();
                if (!my2) return;
                const monthStart = my2.year + '-' + pad(my2.month) + '-01';
                const nowStr = dateStrFromDate(new Date());

                // calendar.js сам ограничивает выбор текущей датой, но всё равно берём "сегодня", если он в этом месяце
                let dateToShow = monthStart;
                if (nowStr >= monthStart && nowStr <= dateStrFromDate(new Date(my2.year, my2.month, 0))) {
                    dateToShow = nowStr;
                }

                window.WaterWizCalendar.setSelectedDate(dateToShow);
                selectedDate = dateToShow;
                if (tasksTitle) tasksTitle.textContent = 'Задачи на ' + formatDateLabel(selectedDate);
                refreshTasks();
            }, 0);
        }
        if (monthEl) monthEl.addEventListener('change', onMonthYearChange);
        if (yearEl) yearEl.addEventListener('change', onMonthYearChange);

        // Filters
        if (locationFilter) {
            locationFilter.addEventListener('change', function () {
                selectedLocationId = locationFilter.value || '';
                refreshTasks();
            });
        }

        // Initial selection + load
        (async function initAll() {
            initWarehouseTabs();

            try {
                await loadLocations();
                await loadUsers();
            } catch (e) {
                showTasksError('Не удалось загрузить справочники (локации/пользователи).');
            }

            const my = window.WaterWizCalendar.getCurrentMonthYear();
            const todayStr = dateStrFromDate(new Date());
            const monthStart = my.year + '-' + pad(my.month) + '-01';
            const dateToShow = todayStr >= monthStart ? todayStr : monthStart;

            window.WaterWizCalendar.setSelectedDate(dateToShow);
            selectedDate = dateToShow;
            if (tasksTitle) tasksTitle.textContent = 'Задачи на ' + formatDateLabel(selectedDate);
            await refreshTasks();
        })();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', wireTasksPage);
    } else {
        wireTasksPage();
    }
})();
