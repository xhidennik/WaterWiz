/**
 * Склад: переключение вкладок и вывод данных из localStorage.
 */

function formatQuantity(num) {
    return String(num).replace(/\B(?=(\d{3})+(?!\d))/g, '\u202f');
}

function renderInventoryTable() {
    const tbody = document.querySelector('#inventory tbody');
    if (!tbody) return;
    const items = getInventory();
    tbody.innerHTML = items.map(function (row) {
        return '<tr><td>' + escapeHtml(row.name) + '</td><td>' + formatQuantity(row.quantity) +
            '</td><td>' + escapeHtml(row.unit) + '</td><td><span class="status status-' + escapeHtml(row.statusType) + '">' +
            escapeHtml(row.status) + '</span></td></tr>';
    }).join('');
}

function renderProductsTable() {
    var tbody = document.querySelector('#products tbody');
    if (!tbody) return;
    var items = getProducts();
    var getImgPath = (typeof getProductImagePath === 'function') ? getProductImagePath : function () { return ''; };
    tbody.innerHTML = items.map(function (row) {
        var imgPath = (row.category && row.name) ? getImgPath(row) : '';
        var imgHtml = imgPath
            ? '<img src="' + escapeAttr(imgPath) + '" alt="" class="product-thumb" onerror="this.style.display=\'none\'">'
            : '';
        return '<tr><td class="products-table__img">' + imgHtml + '</td><td>' + escapeHtml(row.name) + '</td><td>' + formatQuantity(row.quantity) +
            '</td><td>' + escapeHtml(row.unit) + '</td><td><span class="status status-' + escapeHtml(row.statusType) + '">' +
            escapeHtml(row.status) + '</span></td></tr>';
    }).join('');
}

function escapeAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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

function initStoragePage() {
    initWarehouseTabs();
    renderInventoryTable();
    renderProductsTable();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initStoragePage);
} else {
    initStoragePage();
}
