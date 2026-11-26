/**
 * Админка: реальные метрики там, где есть данные; иначе — демо из data-admin.js.
 */

(function () {
    const METRICS_URL = '/api/admin/metrics/';
    const METRICS_POLL_MS = 5000;
    const METRICS_ENABLED = typeof window.WATERWIZ_ADMIN_METRICS_ENABLED !== 'undefined'
        ? window.WATERWIZ_ADMIN_METRICS_ENABLED
        : false;

    let ramData = [];
    let cpuData = [];
    let labels = [];
    let chart = null;
    let pageLoadTime = Date.now();
    let metricsInterval = null;
    let chartDemoInterval = null;
    let diskDemoInterval = null;
    let logDemoInterval = null;
    let lastLogSignature = '';

    let useRealChart = false;
    let useRealDisks = false;
    let useRealLogs = false;

    let demoRam = typeof ADMIN_CHART_INITIAL_RAM !== 'undefined' ? ADMIN_CHART_INITIAL_RAM : 45;
    let demoCpu = typeof ADMIN_CHART_INITIAL_CPU !== 'undefined' ? ADMIN_CHART_INITIAL_CPU : 38;
    let demoDiskPercents = (typeof ADMIN_DEMO_DISKS !== 'undefined' ? ADMIN_DEMO_DISKS : []).map(function (d) {
        return d.percent_init || 50;
    });

    function pad(n) {
        return n < 10 ? '0' + n : String(n);
    }

    function timeLabel() {
        const d = new Date();
        return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function clamp(n, min, max) {
        return Math.max(min, Math.min(max, n));
    }

    function formatUptime(seconds) {
        if (seconds == null || seconds < 0) return null;
        const d = Math.floor(seconds / 86400);
        const h = Math.floor((seconds % 86400) / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        if (d > 0) return d + ' д ' + h + ' ч';
        if (h > 0) return h + ' ч ' + m + ' мин';
        return m + ' мин';
    }

    function formatDemoUptime() {
        const days = typeof ADMIN_SYS_UPTIME_OFFSET_DAYS !== 'undefined' ? ADMIN_SYS_UPTIME_OFFSET_DAYS : 12;
        const hours = typeof ADMIN_SYS_UPTIME_OFFSET_HOURS !== 'undefined' ? ADMIN_SYS_UPTIME_OFFSET_HOURS : 5;
        const elapsed = Date.now() - pageLoadTime;
        return formatUptime(Math.floor(elapsed / 1000) + days * 86400 + hours * 3600);
    }

    function formatGb(gb) {
        if (gb == null) return null;
        if (gb >= 1024) return (gb / 1024).toFixed(1) + ' ТБ';
        return gb.toFixed(1) + ' ГБ';
    }

    function demoNextUpdate() {
        const next = new Date();
        next.setDate(next.getDate() + 1);
        next.setHours(3, 0, 0, 0);
        return next.toLocaleDateString('ru-RU') + ' 03:00';
    }

    function fillInitialChartSlots() {
        const pointsMax = typeof ADMIN_CHART_POINTS_MAX !== 'undefined' ? ADMIN_CHART_POINTS_MAX : 60;
        labels = [];
        ramData = [];
        cpuData = [];
        const now = Date.now();
        for (let i = pointsMax - 1; i >= 0; i--) {
            const t = new Date(now - (pointsMax - 1 - i) * 1000);
            labels.push(pad(t.getHours()) + ':' + pad(t.getMinutes()) + ':' + pad(t.getSeconds()));
            demoRam = clamp(demoRam + (Math.random() - 0.5) * 12, 10, 90);
            demoCpu = clamp(demoCpu + (Math.random() - 0.5) * 10, 5, 85);
            ramData.push(demoRam);
            cpuData.push(demoCpu);
        }
    }

    function initResourcesChart() {
        const canvas = document.getElementById('resourcesLoadChart');
        if (!canvas || typeof Chart === 'undefined') return;
        fillInitialChartSlots();
        const ctx = canvas.getContext('2d');
        const ramColor = typeof ADMIN_CHART_RAM_COLOR !== 'undefined' ? ADMIN_CHART_RAM_COLOR : 'rgba(33, 150, 243, 0.9)';
        const cpuColor = typeof ADMIN_CHART_CPU_COLOR !== 'undefined' ? ADMIN_CHART_CPU_COLOR : 'rgba(76, 175, 80, 0.9)';
        const ramFill = typeof ADMIN_CHART_RAM_FILL !== 'undefined' ? ADMIN_CHART_RAM_FILL : 'rgba(33, 150, 243, 0.1)';
        const cpuFill = typeof ADMIN_CHART_CPU_FILL !== 'undefined' ? ADMIN_CHART_CPU_FILL : 'rgba(76, 175, 80, 0.1)';
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'RAM %',
                        data: ramData,
                        borderColor: ramColor,
                        backgroundColor: ramFill,
                        borderWidth: 2,
                        fill: true,
                        tension: 0.2,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        spanGaps: true,
                    },
                    {
                        label: 'CPU %',
                        data: cpuData,
                        borderColor: cpuColor,
                        backgroundColor: cpuFill,
                        borderWidth: 2,
                        fill: true,
                        tension: 0.2,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        spanGaps: true,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: { legend: { position: 'top' } },
                scales: {
                    x: { display: true, ticks: { maxTicksLimit: 10 } },
                    y: { min: 0, max: 100, title: { display: true, text: '%' } },
                },
            },
        });
    }

    function pushChartPoint(ram, cpu) {
        if (!chart) return;
        labels.shift();
        labels.push(timeLabel());
        ramData.shift();
        cpuData.shift();
        ramData.push(ram);
        cpuData.push(cpu);
        chart.data.labels = labels;
        chart.data.datasets[0].data = ramData;
        chart.data.datasets[1].data = cpuData;
        chart.update('none');
    }

    function tickDemoChart() {
        demoRam = clamp(demoRam + (Math.random() - 0.48) * 14, 8, 92);
        demoCpu = clamp(demoCpu + (Math.random() - 0.5) * 12, 5, 88);
        pushChartPoint(demoRam, demoCpu);
    }

    function setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    function renderDisks(disks) {
        const list = document.getElementById('diskList');
        if (!list) return;
        if (!disks || disks.length === 0) {
            list.innerHTML = '<p class="tasks-empty">Нет данных о дисках.</p>';
            return;
        }
        list.innerHTML = disks.map(function (disk) {
            const pct = disk.percent != null ? disk.percent : 0;
            const used = disk.used_gb != null ? disk.used_gb : 0;
            const total = disk.total_gb != null ? disk.total_gb : 0;
            return '<div class="disk-item">' +
                '<div class="disk-usage__label">' +
                '<span class="disk-item__name">' + escapeHtml(disk.name || disk.mount) + '</span>' +
                '<span class="disk-usage__value disk-item__percent">' + Math.round(pct) + '%</span>' +
                '</div>' +
                '<div class="progress-bar"><div class="progress-bar__fill disk-item__fill" style="width:' + pct + '%"></div></div>' +
                '<div class="disk-usage__meta"><span>' + used + ' ГБ</span> из <span>' + total + ' ГБ</span></div>' +
                '</div>';
        }).join('');
    }

    function buildDemoDisksView() {
        const defs = typeof ADMIN_DEMO_DISKS !== 'undefined' ? ADMIN_DEMO_DISKS : [];
        const dMin = typeof ADMIN_DISK_PERCENT_MIN !== 'undefined' ? ADMIN_DISK_PERCENT_MIN : 40;
        const dMax = typeof ADMIN_DISK_PERCENT_MAX !== 'undefined' ? ADMIN_DISK_PERCENT_MAX : 78;
        return defs.map(function (disk, idx) {
            const total = disk.total_gb || 0;
            let pct = demoDiskPercents[idx];
            if (pct == null) pct = disk.percent_init || 50;
            pct = clamp(pct + (Math.random() - 0.5) * 3.4, dMin, dMax);
            demoDiskPercents[idx] = pct;
            const used = total ? Math.round((pct / 100) * total) : 0;
            return {
                name: disk.name,
                total_gb: total,
                used_gb: used,
                percent: pct,
            };
        });
    }

    function tickDemoDisks() {
        renderDisks(buildDemoDisksView());
    }

    function renderLogEntries(entries) {
        const container = document.getElementById('eventLog');
        if (!container) return;
        const list = entries || [];
        const signature = list.map(function (e) { return (e.time || '') + (e.msg || ''); }).join('|');
        if (signature === lastLogSignature) return;
        lastLogSignature = signature;
        if (list.length === 0) {
            container.innerHTML = '';
            return;
        }
        container.innerHTML = list.map(function (entry) {
            const level = entry.level || 'info';
            return '<div class="event-log__entry event-log__entry--' + escapeHtml(level) + '">' +
                '<span class="event-log__time">' + escapeHtml(entry.time || '') + '</span> ' +
                '<span class="event-log__msg">' + escapeHtml(entry.msg || '') + '</span></div>';
        }).join('');
        container.scrollTop = container.scrollHeight;
    }

    function addDemoLogEntry() {
        const container = document.getElementById('eventLog');
        const templates = typeof ADMIN_EVENT_TEMPLATES !== 'undefined' ? ADMIN_EVENT_TEMPLATES : [];
        if (!container || templates.length === 0) return;
        const template = templates[Math.floor(Math.random() * templates.length)];
        const entry = document.createElement('div');
        entry.className = 'event-log__entry event-log__entry--' + template.level;
        entry.innerHTML = '<span class="event-log__time">' + timeLabel() + '</span> ' +
            '<span class="event-log__msg">' + escapeHtml(template.msg) + '</span>';
        container.appendChild(entry);
        const maxEntries = typeof ADMIN_MAX_LOG_ENTRIES !== 'undefined' ? ADMIN_MAX_LOG_ENTRIES : 80;
        const children = container.querySelectorAll('.event-log__entry');
        if (children.length > maxEntries) children[0].remove();
        container.scrollTop = container.scrollHeight;
        lastLogSignature = '';
    }

    function stopChartDemo() {
        if (chartDemoInterval) {
            clearInterval(chartDemoInterval);
            chartDemoInterval = null;
        }
    }

    function stopDiskDemo() {
        if (diskDemoInterval) {
            clearInterval(diskDemoInterval);
            diskDemoInterval = null;
        }
    }

    function stopLogDemo() {
        if (logDemoInterval) {
            clearInterval(logDemoInterval);
            logDemoInterval = null;
        }
    }

    function startChartDemo() {
        if (chartDemoInterval || useRealChart) return;
        chartDemoInterval = setInterval(tickDemoChart, 1000);
    }

    function startDiskDemo() {
        if (diskDemoInterval || useRealDisks) return;
        tickDemoDisks();
        diskDemoInterval = setInterval(tickDemoDisks, 2000);
    }

    function startLogDemo() {
        if (logDemoInterval || useRealLogs) return;
        const container = document.getElementById('eventLog');
        if (!container) return;
        for (let i = 0; i < 6; i++) addDemoLogEntry();
        logDemoInterval = setInterval(addDemoLogEntry, 2500);
    }

    function syncDemoLoops() {
        if (useRealChart) stopChartDemo();
        else startChartDemo();
        if (useRealDisks) stopDiskDemo();
        else startDiskDemo();
        if (useRealLogs) stopLogDemo();
        else startLogDemo();
    }

    function applyMetrics(data) {
        if (!data) return;

        useRealChart = !!(data.psutil_available && data.ram_percent != null && data.cpu_percent != null);
        useRealDisks = !!(data.disks && data.disks.length > 0);
        useRealLogs = !!(data.log_entries && data.log_entries.length > 0);

        if (useRealChart) {
            pushChartPoint(data.ram_percent, data.cpu_percent);
        }

        if (useRealDisks) {
            renderDisks(data.disks);
        }

        const version = data.app_version || (typeof ADMIN_SYS_VERSION !== 'undefined' ? ADMIN_SYS_VERSION : 'WaterWiz');
        setText('sysVersion', version);
        setText('sysServer', typeof ADMIN_SYS_SERVER !== 'undefined' ? ADMIN_SYS_SERVER : (data.hostname || '—'));
        setText('sysOs', data.os || (typeof ADMIN_SYS_OS !== 'undefined' ? ADMIN_SYS_OS : '—'));

        const uptime = data.uptime_seconds != null ? formatUptime(data.uptime_seconds) : formatDemoUptime();
        setText('sysUptime', uptime || '—');

        const statusEl = document.getElementById('sysStatus');
        if (statusEl) {
            statusEl.textContent = data.status_text || (typeof ADMIN_SYS_STATUS !== 'undefined' ? ADMIN_SYS_STATUS : '—');
            statusEl.classList.remove('sys-info__val--ok', 'sys-info__val--error');
            statusEl.classList.add(data.status_class === 'error' ? 'sys-info__val--error' : 'sys-info__val--ok');
        }

        const sMax = typeof ADMIN_SYS_SESSIONS_MAX !== 'undefined' ? ADMIN_SYS_SESSIONS_MAX : 10;
        if (data.active_sessions != null) {
            setText('sysSessions', data.active_sessions + ' активных');
        } else {
            const sMin = typeof ADMIN_SYS_SESSIONS_MIN !== 'undefined' ? ADMIN_SYS_SESSIONS_MIN : 2;
            const sExtra = typeof ADMIN_SYS_SESSIONS_RANDOM_EXTRA !== 'undefined' ? ADMIN_SYS_SESSIONS_RANDOM_EXTRA : 3;
            setText('sysSessions', (sMin + Math.floor(Math.random() * (sExtra + 1))) + ' из ' + sMax);
        }

        if (data.requests_per_minute != null) {
            setText('sysRpm', data.requests_per_minute + ' req/min');
        } else {
            const rpmMin = typeof ADMIN_SYS_RPM_MIN !== 'undefined' ? ADMIN_SYS_RPM_MIN : 40;
            const rpmExtra = typeof ADMIN_SYS_RPM_RANDOM_EXTRA !== 'undefined' ? ADMIN_SYS_RPM_RANDOM_EXTRA : 35;
            setText('sysRpm', (rpmMin + Math.floor(Math.random() * (rpmExtra + 1))) + ' req/min');
        }

        setText('sysBackup', data.db_backup_at || (typeof ADMIN_SYS_BACKUP_DATE !== 'undefined' ? ADMIN_SYS_BACKUP_DATE : '—'));
        setText('sysNextUpdate', demoNextUpdate());
        setText('sysOnlineUsers', data.online_users != null ? String(data.online_users) : '—');
        setText('sysDjango', data.django_version || '—');

        const ramStat = data.psutil_available && data.ram_total_gb != null
            ? formatGb(data.ram_total_gb)
            : (typeof ADMIN_STAT_RAM_DEMO !== 'undefined' ? ADMIN_STAT_RAM_DEMO : '2 ГБ');
        const cpuStat = data.psutil_available && data.cpu_count
            ? data.cpu_count + ' ядер'
            : (typeof ADMIN_STAT_CPU_DEMO !== 'undefined' ? ADMIN_STAT_CPU_DEMO : '2 ядра');
        const diskStat = data.psutil_available && data.disk_total_gb != null
            ? formatGb(data.disk_total_gb)
            : (typeof ADMIN_STAT_DISK_DEMO !== 'undefined' ? ADMIN_STAT_DISK_DEMO : '128 ГБ');

        setText('statRam', ramStat || '—');
        setText('statCpu', cpuStat || '—');
        setText('statDisk', diskStat || '—');
        setText('statNetwork', typeof ADMIN_STAT_NETWORK_DEMO !== 'undefined' ? ADMIN_STAT_NETWORK_DEMO : '1 Гбит/с');

        if (useRealLogs) {
            renderLogEntries(data.log_entries);
        }

        syncDemoLoops();
    }

    function startDemoOnlyMode() {
        useRealChart = false;
        useRealDisks = false;
        useRealLogs = false;
        setText('sysVersion', typeof ADMIN_SYS_VERSION !== 'undefined' ? ADMIN_SYS_VERSION : 'WaterWiz');
        setText('sysServer', typeof ADMIN_SYS_SERVER !== 'undefined' ? ADMIN_SYS_SERVER : '—');
        setText('sysOs', typeof ADMIN_SYS_OS !== 'undefined' ? ADMIN_SYS_OS : '—');
        setText('sysUptime', formatDemoUptime() || '—');
        setText('sysStatus', typeof ADMIN_SYS_STATUS !== 'undefined' ? ADMIN_SYS_STATUS : '—');
        setText('sysBackup', typeof ADMIN_SYS_BACKUP_DATE !== 'undefined' ? ADMIN_SYS_BACKUP_DATE : '—');
        setText('sysNextUpdate', demoNextUpdate());
        setText('statRam', typeof ADMIN_STAT_RAM_DEMO !== 'undefined' ? ADMIN_STAT_RAM_DEMO : '2 ГБ');
        setText('statCpu', typeof ADMIN_STAT_CPU_DEMO !== 'undefined' ? ADMIN_STAT_CPU_DEMO : '2 ядра');
        setText('statDisk', typeof ADMIN_STAT_DISK_DEMO !== 'undefined' ? ADMIN_STAT_DISK_DEMO : '128 ГБ');
        setText('statNetwork', typeof ADMIN_STAT_NETWORK_DEMO !== 'undefined' ? ADMIN_STAT_NETWORK_DEMO : '1 Гбит/с');
        syncDemoLoops();
    }

    async function pollMetrics() {
        try {
            const res = await fetch(METRICS_URL, { method: 'GET', credentials: 'same-origin' });
            if (!res.ok) return;
            const data = await res.json();
            applyMetrics(data);
        } catch (e) {
            /* ignore */
        }
    }

    function stopAllIntervals() {
        stopChartDemo();
        stopDiskDemo();
        stopLogDemo();
        if (metricsInterval) {
            clearInterval(metricsInterval);
            metricsInterval = null;
        }
    }

    function startMetricsPolling() {
        if (!METRICS_ENABLED) {
            startDemoOnlyMode();
            return;
        }
        stopAllIntervals();
        pollMetrics();
        metricsInterval = setInterval(pollMetrics, METRICS_POLL_MS);
    }

    function initAdminTabs() {
        const tabs = document.querySelectorAll('.admin-tab');
        const contents = document.querySelectorAll('.admin-content');
        if (!tabs.length || !contents.length) return;
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

    function init() {
        pageLoadTime = Date.now();
        initAdminTabs();
        initResourcesChart();
        startMetricsPolling();
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) stopAllIntervals();
            else startMetricsPolling();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
