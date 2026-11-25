/**
 * Данные склада по умолчанию и работа с localStorage.
 * Продукция фермы берётся из data-products.js (единый справочник).
 */

const STORAGE_KEYS = {
    INVENTORY: 'waterwiz_inventory',
    PRODUCTS: 'waterwiz_products'
};

/** Инвентарный склад: наименование, количество, единица, статус, тип цвета */
const DEFAULT_INVENTORY = [
    { name: 'Семена картофеля "Адретта"', quantity: 120, unit: 'кг', status: 'В наличии', statusType: 'success' },
    { name: 'Семена томатов "Бычье сердце"', quantity: 45, unit: 'упак.', status: 'В наличии', statusType: 'success' },
    { name: 'Семена огурцов "Муравей"', quantity: 18, unit: 'упак.', status: 'Заканчиваются', statusType: 'warning' },
    { name: 'Удобрение "Гумат калия"', quantity: 85, unit: 'л', status: 'В наличии', statusType: 'success' },
    { name: 'Дизельное топливо', quantity: 420, unit: 'л', status: 'В наличии', statusType: 'success' },
    { name: 'Запчасти для ДТ-75', quantity: 12, unit: 'компл.', status: 'Резерв', statusType: 'info' },
    { name: 'Инструменты (лопаты, грабли)', quantity: 28, unit: 'шт', status: 'В наличии', statusType: 'success' }
];

/** Продукция фермы: из справочника продуктов + объём/статус. По умолчанию генерируется из getAllProducts(). */
function buildDefaultProducts() {
    if (typeof getAllProducts !== 'function') {
        return [];
    }
    var list = getAllProducts();
    return list.map(function (p, i) {
        var q = (i % 3 === 0) ? 80 + (i * 12) % 400 : (i % 5 === 0) ? 15 + (i * 3) % 80 : 200 + (i * 7) % 600;
        var statusType = (i % 7 === 0) ? 'warning' : 'success';
        var status = statusType === 'warning' ? 'К отгрузке' : 'На складе';
        var unit = (p.category === 'zelen') ? 'уп.' : 'кг';
        return {
            category: p.category,
            name: p.name,
            quantity: q,
            unit: unit,
            status: status,
            statusType: statusType
        };
    });
}

function getInventory() {
    try {
        var raw = localStorage.getItem(STORAGE_KEYS.INVENTORY);
        if (raw) return JSON.parse(raw);
    } catch (e) {}
    return JSON.parse(JSON.stringify(DEFAULT_INVENTORY));
}

function getProducts() {
    try {
        var raw = localStorage.getItem(STORAGE_KEYS.PRODUCTS);
        if (raw) return JSON.parse(raw);
        var copy = buildDefaultProducts();
        if (copy.length > 0) {
            setProducts(copy);
            return copy;
        }
    } catch (e) {}
    return buildDefaultProducts();
}

function setInventory(items) {
    localStorage.setItem(STORAGE_KEYS.INVENTORY, JSON.stringify(items));
}

function setProducts(items) {
    localStorage.setItem(STORAGE_KEYS.PRODUCTS, JSON.stringify(items));
}

/** Сброс инвентаря к дефолту (продукция пересобирается из справочника) */
function resetStorageToDefaults() {
    localStorage.setItem(STORAGE_KEYS.INVENTORY, JSON.stringify(DEFAULT_INVENTORY));
    setProducts(buildDefaultProducts());
}
