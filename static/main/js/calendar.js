/**
 * Календарь на любой месяц в диапазоне январь 2016 — февраль 2026.
 * Месяц и год задаются выпадающими списками.
 */

(function () {
    const MIN_YEAR = 2016;
    const MIN_MONTH = 1;
    // Ограничиваем календарь текущей датой
    const now = new Date();
    const MAX_YEAR = now.getFullYear();
    const MAX_MONTH = now.getMonth() + 1;

    const MONTH_NAMES = [
        'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
        'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
    ];

    const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

    function clampMonthYear(month, year) {
        if (year < MIN_YEAR) {
            year = MIN_YEAR;
            month = MIN_MONTH;
        } else if (year > MAX_YEAR) {
            year = MAX_YEAR;
            month = MAX_MONTH;
        } else if (year === MIN_YEAR && month < MIN_MONTH) {
            month = MIN_MONTH;
        } else if (year === MAX_YEAR && month > MAX_MONTH) {
            month = MAX_MONTH;
        }
        return { month: month, year: year };
    }

    /** Понедельник = 0 */
    function getDayOfWeek(date) {
        return (date.getDay() + 6) % 7;
    }

    function getDaysInMonth(year, month) {
        return new Date(year, month, 0).getDate();
    }

    function dateString(year, month, day) {
        var m = month < 10 ? '0' + month : String(month);
        var d = day < 10 ? '0' + day : String(day);
        return year + '-' + m + '-' + d;
    }

    function isToday(year, month, day) {
        var d = new Date();
        return d.getFullYear() === year && d.getMonth() + 1 === month && d.getDate() === day;
    }

    var currentMonth = new Date().getMonth() + 1;
    var currentYear = new Date().getFullYear();
    var selectedDate = null;
    var onDaySelectCallback = null;

    function fillYearSelect(selectEl) {
        if (!selectEl) return;
        selectEl.innerHTML = '';
        for (var y = MIN_YEAR; y <= MAX_YEAR; y++) {
            var opt = document.createElement('option');
            opt.value = y;
            opt.textContent = y;
            if (y === currentYear) opt.selected = true;
            selectEl.appendChild(opt);
        }
    }

    function fillMonthSelect(selectEl, year) {
        if (!selectEl) return;
        selectEl.innerHTML = '';
        var start = (year === MIN_YEAR) ? MIN_MONTH : 1;
        var end = (year === MAX_YEAR) ? MAX_MONTH : 12;
        for (var m = start; m <= end; m++) {
            var opt = document.createElement('option');
            opt.value = m;
            opt.textContent = MONTH_NAMES[m - 1];
            if (m === currentMonth) opt.selected = true;
            selectEl.appendChild(opt);
        }
    }

    function renderGrid(container, year, month) {
        if (!container) return;
        var c = clampMonthYear(month, year);
        month = c.month;
        year = c.year;

        var first = new Date(year, month - 1, 1);
        var offset = getDayOfWeek(first);
        var daysInMonth = getDaysInMonth(year, month);

        container.innerHTML = '';

        WEEKDAYS.forEach(function (wd) {
            var h = document.createElement('div');
            h.className = 'calendar-header';
            h.textContent = wd;
            container.appendChild(h);
        });

        for (var i = 0; i < offset; i++) {
            var empty = document.createElement('div');
            empty.className = 'calendar-day calendar-day--empty';
            container.appendChild(empty);
        }

        for (var day = 1; day <= daysInMonth; day++) {
            var cell = document.createElement('div');
            cell.className = 'calendar-day';
            cell.textContent = day;
            cell.setAttribute('data-date', dateString(year, month, day));
            if (isToday(year, month, day)) cell.classList.add('today');
            if (selectedDate === dateString(year, month, day)) cell.classList.add('selected');
            cell.addEventListener('click', function () {
                var date = this.getAttribute('data-date');
                if (!date) return;
                selectedDate = date;
                container.querySelectorAll('.calendar-day[data-date]').forEach(function (el) {
                    el.classList.remove('selected');
                    if (el.getAttribute('data-date') === date) el.classList.add('selected');
                });
                if (onDaySelectCallback) onDaySelectCallback(date);
            });
            container.appendChild(cell);
        }
    }

    function updateCalendar() {
        var monthEl = document.getElementById('calendarMonth');
        var yearEl = document.getElementById('calendarYear');
        var gridEl = document.getElementById('calendarGrid');
        if (!monthEl || !yearEl || !gridEl) return;

        var year = parseInt(yearEl.value, 10);
        var month = parseInt(monthEl.value, 10);
        var c = clampMonthYear(month, year);
        month = c.month;
        year = c.year;

        fillMonthSelect(monthEl, year);
        monthEl.value = String(month);
        renderGrid(gridEl, year, month);
    }

    function setSelectedDate(dateStr) {
        selectedDate = dateStr;
        var gridEl = document.getElementById('calendarGrid');
        if (!gridEl) return;
        gridEl.querySelectorAll('.calendar-day[data-date]').forEach(function (el) {
            el.classList.toggle('selected', el.getAttribute('data-date') === dateStr);
        });
    }

    function initCalendar(onDaySelect) {
        onDaySelectCallback = onDaySelect;

        var monthEl = document.getElementById('calendarMonth');
        var yearEl = document.getElementById('calendarYear');
        var gridEl = document.getElementById('calendarGrid');
        if (!gridEl) return;

        var now = new Date();
        currentYear = now.getFullYear();
        currentMonth = now.getMonth() + 1;
        if (currentYear > MAX_YEAR || (currentYear === MAX_YEAR && currentMonth > MAX_MONTH)) {
            currentYear = MAX_YEAR;
            currentMonth = MAX_MONTH;
        }
        if (currentYear < MIN_YEAR) {
            currentYear = MIN_YEAR;
            currentMonth = MIN_MONTH;
        }

        fillYearSelect(yearEl);
        fillMonthSelect(monthEl, currentYear);
        monthEl.value = String(currentMonth);
        yearEl.value = String(currentYear);

        yearEl.addEventListener('change', updateCalendar);
        monthEl.addEventListener('change', updateCalendar);

        renderGrid(gridEl, currentYear, currentMonth);
    }

    window.WaterWizCalendar = {
        init: initCalendar,
        setSelectedDate: setSelectedDate,
        getCurrentMonthYear: function () {
            var y = document.getElementById('calendarYear');
            var m = document.getElementById('calendarMonth');
            if (!y || !m) return { month: currentMonth, year: currentYear };
            return { month: parseInt(m.value, 10), year: parseInt(y.value, 10) };
        },
        update: updateCalendar
    };
})();
