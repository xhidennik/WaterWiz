/**
 * Админка: динамические графики RAM/CPU, лог событий, прогресс диска, системная информация.
 * Все данные условные и генерируются на лету.
 */

(function () {
    let ramData = [];
    let cpuData = [];
    let labels = [];
    let chart = null;
    let diskPercent = typeof ADMIN_DISK_PERCENT_INIT !== 'undefined' ? ADMIN_DISK_PERCENT_INIT : 62;
    let lastRam = typeof ADMIN_CHART_INITIAL_RAM !== 'undefined' ? ADMIN_CHART_INITIAL_RAM : 45;
    let lastCpu = typeof ADMIN_CHART_INITIAL_CPU !== 'undefined' ? ADMIN_CHART_INITIAL_CPU : 38;
    let pageLoadTime = Date.now();
    let logInterval = null;
    let chartInterval = null;
    let diskInterval = null;
    let sysInterval = null;

    function pad(n) {
        return n < 10 ? '0' + n : String(n);
    }

    function timeLabel() {
        const d = new Date();
        return pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
    }

    function fillInitialData() {
        const pointsMax = typeof ADMIN_CHART_POINTS_MAX !== 'undefined' ? ADMIN_CHART_POINTS_MAX : 60;
        const now = Date.now();
        for (let i = pointsMax - 1; i >= 0; i--) {
            const t = new Date(now - (pointsMax - 1 - i) * 1000);
            labels.push(pad(t.getHours()) + ':' + pad(t.getMinutes()) + ':' + pad(t.getSeconds()));
            lastRam = Math.max(10, Math.min(90, lastRam + (Math.random() - 0.5) * 12));
            lastCpu = Math.max(5, Math.min(85, lastCpu + (Math.random() - 0.5) * 10));
            ramData.push(lastRam);
            cpuData.push(lastCpu);
        }
    }

    function initResourcesChart() {
        const canvas = document.getElementById('resourcesLoadChart');
        if (!canvas) return;
        fillInitialData();
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
                        pointHoverRadius: 4
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
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                plugins: {
                    legend: { position: 'top' }
                },
                scales: {
                    x: {
                        display: true,
                        ticks: { maxTicksLimit: 10 }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        title: { display: true, text: '%' }
                    }
                }
            }
        });
    }

    function tickChart() {
        if (!chart) return;
        labels.shift();
        labels.push(timeLabel());
        lastRam = Math.max(8, Math.min(92, lastRam + (Math.random() - 0.48) * 14));
        lastCpu = Math.max(5, Math.min(88, lastCpu + (Math.random() - 0.5) * 12));
        ramData.shift();
        cpuData.shift();
        ramData.push(lastRam);
        cpuData.push(lastCpu);
        chart.data.labels = labels;
        chart.data.datasets[0].data = ramData;
        chart.data.datasets[1].data = cpuData;
        chart.update('none');
    }

    function addLogEntry() {
        const container = document.getElementById('eventLog');
        if (!container) return;
        const templates = typeof ADMIN_EVENT_TEMPLATES !== 'undefined' ? ADMIN_EVENT_TEMPLATES : [];
        if (templates.length === 0) return;
        const t = new Date();
        const timeStr = pad(t.getHours()) + ':' + pad(t.getMinutes()) + ':' + pad(t.getSeconds());
        const template = templates[Math.floor(Math.random() * templates.length)];
        const entry = document.createElement('div');
        entry.className = 'event-log__entry event-log__entry--' + template.level;
        entry.innerHTML = '<span class="event-log__time">' + timeStr + '</span> ' +
            '<span class="event-log__msg">' + escapeHtml(template.msg) + '</span>';
        container.appendChild(entry);
        const children = container.querySelectorAll('.event-log__entry');
        const maxEntries = typeof ADMIN_MAX_LOG_ENTRIES !== 'undefined' ? ADMIN_MAX_LOG_ENTRIES : 80;
        if (children.length > maxEntries) {
            children[0].remove();
        }
        container.scrollTop = container.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function updateDiskBar() {
        const dMin = typeof ADMIN_DISK_PERCENT_MIN !== 'undefined' ? ADMIN_DISK_PERCENT_MIN : 40;
        const dMax = typeof ADMIN_DISK_PERCENT_MAX !== 'undefined' ? ADMIN_DISK_PERCENT_MAX : 78;
        diskPercent = Math.max(dMin, Math.min(dMax, diskPercent + (Math.random() - 0.5) * 4));
        const total = typeof ADMIN_DISK_TOTAL_GB !== 'undefined' ? ADMIN_DISK_TOTAL_GB : 128;
        const used = Math.round((diskPercent / 100) * total);
        const elPercent = document.getElementById('diskPercent');
        const elProgress = document.getElementById('diskProgress');
        const elUsed = document.getElementById('diskUsed');
        const elTotal = document.getElementById('diskTotal');
        if (elPercent) elPercent.textContent = Math.round(diskPercent) + '%';
        if (elProgress) elProgress.style.width = diskPercent + '%';
        if (elUsed) elUsed.textContent = used + ' ГБ';
        if (elTotal) elTotal.textContent = total + ' ГБ';
    }

    function getUptimeOffsetMs() {
        const days = typeof ADMIN_SYS_UPTIME_OFFSET_DAYS !== 'undefined' ? ADMIN_SYS_UPTIME_OFFSET_DAYS : 12;
        const hours = typeof ADMIN_SYS_UPTIME_OFFSET_HOURS !== 'undefined' ? ADMIN_SYS_UPTIME_OFFSET_HOURS : 5;
        return 86400000 * days + 3600000 * hours;
    }

    function formatUptime(ms) {
        const s = Math.floor(ms / 1000) % 60;
        const m = Math.floor(ms / 60000) % 60;
        const h = Math.floor(ms / 3600000) % 24;
        const d = Math.floor(ms / 86400000);
        if (d > 0) return d + ' д ' + h + ' ч';
        if (h > 0) return h + ' ч ' + m + ' мин';
        return m + ' мин ' + s + ' с';
    }

    function updateSystemInfo() {
        const elapsed = Date.now() - pageLoadTime;
        const set = function (id, val) { const el = document.getElementById(id); if (el) el.textContent = val; };
        set('sysVersion', typeof ADMIN_SYS_VERSION !== 'undefined' ? ADMIN_SYS_VERSION : 'WaterWiz v2.4.1');
        set('sysServer', typeof ADMIN_SYS_SERVER !== 'undefined' ? ADMIN_SYS_SERVER : 'srv-farm-01.everygreen.local');
        set('sysOs', typeof ADMIN_SYS_OS !== 'undefined' ? ADMIN_SYS_OS : 'Ubuntu 22.04 LTS');
        const uptimeEl = document.getElementById('sysUptime');
        if (uptimeEl) uptimeEl.textContent = formatUptime(elapsed + getUptimeOffsetMs());
        set('sysStatus', typeof ADMIN_SYS_STATUS !== 'undefined' ? ADMIN_SYS_STATUS : 'Работает стабильно');
        const sMin = typeof ADMIN_SYS_SESSIONS_MIN !== 'undefined' ? ADMIN_SYS_SESSIONS_MIN : 2;
        const sExtra = typeof ADMIN_SYS_SESSIONS_RANDOM_EXTRA !== 'undefined' ? ADMIN_SYS_SESSIONS_RANDOM_EXTRA : 3;
        const sMax = typeof ADMIN_SYS_SESSIONS_MAX !== 'undefined' ? ADMIN_SYS_SESSIONS_MAX : 10;
        const sessions = sMin + Math.floor(Math.random() * (sExtra + 1));
        set('sysSessions', sessions + ' из ' + sMax);
        const rpmMin = typeof ADMIN_SYS_RPM_MIN !== 'undefined' ? ADMIN_SYS_RPM_MIN : 40;
        const rpmExtra = typeof ADMIN_SYS_RPM_RANDOM_EXTRA !== 'undefined' ? ADMIN_SYS_RPM_RANDOM_EXTRA : 35;
        set('sysRpm', (rpmMin + Math.floor(Math.random() * (rpmExtra + 1))) + ' req/min');
        set('sysBackup', typeof ADMIN_SYS_BACKUP_DATE !== 'undefined' ? ADMIN_SYS_BACKUP_DATE : '28.01.2026 03:00');
        const next = new Date();
        next.setDate(next.getDate() + 1);
        next.setHours(3, 0, 0, 0);
        set('sysNextUpdate', next.toLocaleDateString('ru-RU') + ' 03:00');
    }

    function startIntervals() {
        chartInterval = setInterval(tickChart, 1000);
        logInterval = setInterval(addLogEntry, 2500);
        diskInterval = setInterval(updateDiskBar, 2000);
        updateDiskBar();
        updateSystemInfo();
        sysInterval = setInterval(updateSystemInfo, 5000);
        for (var i = 0; i < 8; i++) addLogEntry();
    }

    function stopIntervals() {
        if (chartInterval) clearInterval(chartInterval);
        if (logInterval) clearInterval(logInterval);
        if (diskInterval) clearInterval(diskInterval);
        if (sysInterval) clearInterval(sysInterval);
    }

    function init() {
        if (!document.getElementById('resourcesLoadChart')) return;
        initResourcesChart();
        startIntervals();
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) stopIntervals();
            else startIntervals();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
