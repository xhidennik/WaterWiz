// Chart initialization — категории продукции JGC Evergreen (Огурцы, Зелень, Редис, Кабачок, Томаты)
function initCharts() {
    const yieldCtx = document.getElementById('yieldChart');
    if (yieldCtx) {
        new Chart(yieldCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь'],
                datasets: [
                    { label: 'Огурцы (кг)', data: [1850, 3650, 5200, 6420, 7450, 8230], borderColor: '#43a047', backgroundColor: 'rgba(67, 160, 71, 0.1)', borderWidth: 3, fill: true, tension: 0.3 },
                    { label: 'Зелень (кг)', data: [420, 880, 1320, 1780, 2240, 2680], borderColor: '#2e7d32', backgroundColor: 'rgba(46, 125, 50, 0.1)', borderWidth: 3, fill: true, tension: 0.3 },
                    { label: 'Редис (кг)', data: [320, 650, 980, 1320, 1650, 1980], borderColor: '#8e24aa', backgroundColor: 'rgba(142, 36, 170, 0.1)', borderWidth: 3, fill: true, tension: 0.3 },
                    { label: 'Кабачок (кг)', data: [280, 560, 840, 1120, 1400, 1680], borderColor: '#5d4037', backgroundColor: 'rgba(93, 64, 55, 0.1)', borderWidth: 3, fill: true, tension: 0.3 },
                    { label: 'Томаты (кг)', data: [1250, 2850, 4200, 5800, 7350, 8920], borderColor: '#e53935', backgroundColor: 'rgba(229, 57, 53, 0.1)', borderWidth: 3, fill: true, tension: 0.3 }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Килограммы'
                        }
                    }
                }
            }
        });
    }

    const waterCtx = document.getElementById('waterChart');
    if (waterCtx) {
        new Chart(waterCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['Огурцы', 'Зелень', 'Редис', 'Кабачок', 'Томаты'],
                datasets: [{
                    label: 'Средний расход воды (л/сутки)',
                    data: [2850, 1200, 450, 680, 3200],
                    backgroundColor: ['rgba(67, 160, 71, 0.8)', 'rgba(46, 125, 50, 0.8)', 'rgba(142, 36, 170, 0.8)', 'rgba(93, 64, 55, 0.8)', 'rgba(229, 57, 53, 0.8)'],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Литры в сутки'
                        }
                    }
                }
            }
        });
    }

    const resourcesCtx = document.getElementById('resourcesChart');
    if (resourcesCtx) {
        new Chart(resourcesCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Огурцы', 'Зелень', 'Редис', 'Кабачок', 'Томаты'],
                datasets: [{
                    data: [30, 20, 5, 8, 37],
                    backgroundColor: ['#43a047', '#2e7d32', '#8e24aa', '#5d4037', '#e53935'],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += context.parsed + '%';
                                return label;
                            }
                        }
                    }
                },
                cutout: '60%'
            }
        });
    }
}