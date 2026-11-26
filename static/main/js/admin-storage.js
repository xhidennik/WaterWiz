/**
 * Админка: редактирование склада (только для staff).
 */
(function () {
    const apiBase = '/api/storage';

    const STATUS_LABELS = {
        in_stock: 'В наличии',
        running_low: 'Заканчиваются',
        reserved: 'Резерв',
    };

    const STATUS_BADGE = {
        in_stock: 'badge-success',
        running_low: 'badge-warning',
        reserved: 'badge-secondary',
    };

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }

    function getCsrfToken() {
        const el = document.querySelector('#storageForm input[name="csrfmiddlewaretoken"]');
        return el ? el.value : '';
    }

    async function apiFetchJson(url, options) {
        const res = await fetch(url, options);
        if (!res.ok) {
            const txt = await res.text().catch(function () { return ''; });
            throw new Error(txt || ('HTTP ' + res.status));
        }
        return res.json();
    }

    function initStorageWarehouseTabs(root) {
        const tabs = root.querySelectorAll('[data-storage-tab]');
        const contents = root.querySelectorAll('.warehouse-content[data-storage-category]');
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                const tabId = tab.getAttribute('data-storage-tab');
                tabs.forEach(function (t) { t.classList.remove('active'); });
                contents.forEach(function (c) {
                    c.classList.remove('active');
                    if (c.id === tabId) c.classList.add('active');
                });
                tab.classList.add('active');
            });
        });
    }

    function wireStorageAdmin() {
        const root = document.getElementById('admin-storage');
        if (!root) return;

        const inventoryBody = document.getElementById('adminInventoryBody');
        const productsBody = document.getElementById('adminProductsBody');
        const errInventory = document.getElementById('storageAdminErrorInventory');
        const errProducts = document.getElementById('storageAdminErrorProducts');

        const overlayEl = document.getElementById('storageModalOverlay');
        const modalEl = document.getElementById('storageModal');
        const formEl = document.getElementById('storageForm');
        const itemIdEl = document.getElementById('storageItemId');
        const categoryEl = document.getElementById('storageCategory');
        const modalTitleEl = document.getElementById('storageModalTitle');
        const nameEl = document.getElementById('storageName');
        const quantityEl = document.getElementById('storageQuantity');
        const unitEl = document.getElementById('storageUnit');
        const statusEl = document.getElementById('storageStatus');
        const cancelBtn = document.getElementById('storageCancelBtn');
        const formErrorEl = document.getElementById('storageFormError');

        const csrfToken = getCsrfToken();
        let currentCategory = 'inventory';

        function showListError(category, msg) {
            const el = category === 'products' ? errProducts : errInventory;
            if (!el) return;
            el.textContent = msg || '';
            el.style.display = msg ? 'block' : 'none';
        }

        function hideFormError() {
            if (!formErrorEl) return;
            formErrorEl.textContent = '';
            formErrorEl.style.display = 'none';
        }

        function showFormError(msg) {
            if (!formErrorEl) return;
            formErrorEl.textContent = msg || '';
            formErrorEl.style.display = 'block';
        }

        function openModal() {
            if (overlayEl) overlayEl.classList.add('active');
            if (modalEl) modalEl.classList.add('active');
        }

        function closeModal() {
            if (overlayEl) overlayEl.classList.remove('active');
            if (modalEl) modalEl.classList.remove('active');
            hideFormError();
        }

        function renderStatusBadge(status) {
            const label = STATUS_LABELS[status] || status;
            const cls = STATUS_BADGE[status] || 'badge-secondary';
            return '<span class="badge ' + cls + '">' + escapeHtml(label) + '</span>';
        }

        function renderRow(item) {
            return '<tr data-id="' + item.id + '">' +
                '<td>' + escapeHtml(item.name) + '</td>' +
                '<td>' + escapeHtml(item.quantity) + '</td>' +
                '<td>' + escapeHtml(item.unit) + '</td>' +
                '<td>' + renderStatusBadge(item.status) + '</td>' +
                '<td class="storage-admin-actions">' +
                '<button type="button" class="btn btn-info btn-sm" data-storage-edit="' + item.id + '"><i class="fas fa-pen"></i></button> ' +
                '<button type="button" class="btn btn-info btn-sm" data-storage-delete="' + item.id + '"><i class="fas fa-trash"></i></button>' +
                '</td></tr>';
        }

        function renderTable(category, items) {
            const tbody = category === 'products' ? productsBody : inventoryBody;
            if (!tbody) return;
            if (!items || items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5">Нет позиций.</td></tr>';
                return;
            }
            tbody.innerHTML = items.map(renderRow).join('');
        }

        async function loadCategory(category) {
            showListError(category, '');
            const data = await apiFetchJson(apiBase + '/?category=' + encodeURIComponent(category), {
                method: 'GET',
                credentials: 'same-origin',
            });
            renderTable(category, data.items || []);
        }

        async function reloadAll() {
            await Promise.all([loadCategory('inventory'), loadCategory('products')]);
        }

        function openCreate(category) {
            currentCategory = category;
            if (itemIdEl) itemIdEl.value = '';
            if (categoryEl) categoryEl.value = category;
            if (modalTitleEl) modalTitleEl.textContent = 'Новая позиция';
            if (nameEl) nameEl.value = '';
            if (quantityEl) quantityEl.value = '1';
            if (unitEl) unitEl.value = 'шт';
            if (statusEl) statusEl.value = 'in_stock';
            hideFormError();
            openModal();
        }

        function openEdit(item) {
            currentCategory = item.category;
            if (itemIdEl) itemIdEl.value = String(item.id);
            if (categoryEl) categoryEl.value = item.category;
            if (modalTitleEl) modalTitleEl.textContent = 'Редактирование';
            if (nameEl) nameEl.value = item.name || '';
            if (quantityEl) quantityEl.value = String(item.quantity || 1);
            if (unitEl) unitEl.value = item.unit || '';
            if (statusEl) statusEl.value = item.status || 'in_stock';
            hideFormError();
            openModal();
        }

        async function findItemById(id) {
            const data = await apiFetchJson(apiBase + '/', { method: 'GET', credentials: 'same-origin' });
            const items = data.items || [];
            for (let i = 0; i < items.length; i++) {
                if (String(items[i].id) === String(id)) return items[i];
            }
            return null;
        }

        root.querySelectorAll('[data-storage-add]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                openCreate(btn.getAttribute('data-storage-add') || 'inventory');
            });
        });

        root.addEventListener('click', async function (e) {
            const editBtn = e.target.closest('[data-storage-edit]');
            const deleteBtn = e.target.closest('[data-storage-delete]');
            if (editBtn) {
                const id = editBtn.getAttribute('data-storage-edit');
                try {
                    const item = await findItemById(id);
                    if (!item) throw new Error('Позиция не найдена');
                    openEdit(item);
                } catch (err) {
                    const panel = editBtn.closest('[data-storage-category]');
                    const cat = panel ? panel.getAttribute('data-storage-category') : 'inventory';
                    showListError(cat, err.message || 'Ошибка загрузки');
                }
                return;
            }
            if (deleteBtn) {
                const id = deleteBtn.getAttribute('data-storage-delete');
                if (!window.confirm('Удалить позицию со склада?')) return;
                const panel = deleteBtn.closest('[data-storage-category]');
                const cat = panel ? panel.getAttribute('data-storage-category') : 'inventory';
                try {
                    await apiFetchJson(apiBase + '/' + encodeURIComponent(id) + '/', {
                        method: 'DELETE',
                        credentials: 'same-origin',
                        headers: { 'X-CSRFToken': csrfToken },
                    });
                    await reloadAll();
                } catch (err) {
                    showListError(cat, err.message || 'Не удалось удалить');
                }
            }
        });

        if (cancelBtn) {
            cancelBtn.addEventListener('click', closeModal);
        }
        if (overlayEl) {
            overlayEl.addEventListener('click', closeModal);
        }

        if (formEl) {
            formEl.addEventListener('submit', async function (e) {
                e.preventDefault();
                hideFormError();

                const payload = {
                    name: nameEl ? nameEl.value.trim() : '',
                    quantity: quantityEl ? parseInt(quantityEl.value, 10) : 1,
                    unit: unitEl ? unitEl.value.trim() : '',
                    status: statusEl ? statusEl.value : 'in_stock',
                    category: categoryEl ? categoryEl.value : currentCategory,
                };

                const id = itemIdEl ? itemIdEl.value : '';
                try {
                    if (id) {
                        await apiFetchJson(apiBase + '/' + encodeURIComponent(id) + '/', {
                            method: 'PUT',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken,
                            },
                            body: JSON.stringify(payload),
                        });
                    } else {
                        await apiFetchJson(apiBase + '/', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken,
                            },
                            body: JSON.stringify(payload),
                        });
                    }
                    closeModal();
                    await reloadAll();
                } catch (err) {
                    showFormError(err.message || 'Не удалось сохранить');
                }
            });
        }

        initStorageWarehouseTabs(root);
        reloadAll().catch(function (err) {
            showListError('inventory', err.message || 'Ошибка загрузки склада');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', wireStorageAdmin);
    } else {
        wireStorageAdmin();
    }
})();
