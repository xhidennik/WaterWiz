/**
 * Единый справочник продукции JGC Evergreen.
 * Используется на складе, дашборде и везде, где нужен список продукции.
 * Фото: img/products/{категория}/{название}.png (название — как в поле name).
 */

/** Ключ категории → подпись для интерфейса */
const PRODUCT_CATEGORIES = {
    ogurcy: 'Огурцы',
    zelen: 'Зелень',
    redis: 'Редис',
    kabachok: 'Кабачок',
    tomaty: 'Томаты'
};

/** Все продукты: категория (ключ папки), название (имя файла без .png) */
const PRODUCTS_LIST = [
    // Огурцы
    { category: 'ogurcy', name: 'Коктейльный огурец' },
    { category: 'ogurcy', name: 'Короткоплодный огурец' },
    { category: 'ogurcy', name: 'Среднеплодный огурец' },
    // Зелень
    { category: 'zelen', name: 'Розмарин' },
    { category: 'zelen', name: 'Тимьян' },
    { category: 'zelen', name: 'Мелисса' },
    { category: 'zelen', name: 'Сельдерей' },
    { category: 'zelen', name: 'Укроп' },
    { category: 'zelen', name: 'Щавель' },
    { category: 'zelen', name: 'Петрушка' },
    { category: 'zelen', name: 'Мангольд' },
    { category: 'zelen', name: 'Базилик красный' },
    { category: 'zelen', name: 'Базилик зелёный' },
    { category: 'zelen', name: 'Руккола' },
    { category: 'zelen', name: 'Салат мини-ромен' },
    { category: 'zelen', name: 'Салат листовой' },
    // Редис
    { category: 'redis', name: 'Редис' },
    // Кабачок
    { category: 'kabachok', name: 'Кабачок зелёный' },
    { category: 'kabachok', name: 'Кабачок белый' },
    // Томаты
    { category: 'tomaty', name: 'Черри овальные' },
    { category: 'tomaty', name: 'Черри желтые' },
    { category: 'tomaty', name: 'Черри красные' },
    { category: 'tomaty', name: 'Красный кистевой томат' },
    { category: 'tomaty', name: 'Красный крупноплодный томат' },
    { category: 'tomaty', name: 'Розовый томат' }
];

/** Путь к фото продукта: img/products/{категория}/{название}.png */
function getProductImagePath(product) {
    if (!product || !product.category || !product.name) return '';
    return 'img/products/' + product.category + '/' + product.name + '.png';
}

/** Все продукты плоским массивом */
function getAllProducts() {
    return PRODUCTS_LIST.slice();
}

/** Продукты по категории */
function getProductsByCategory(categoryKey) {
    return PRODUCTS_LIST.filter(function (p) { return p.category === categoryKey; });
}

/** Список ключей категорий в порядке отображения */
function getCategoryKeys() {
    return ['ogurcy', 'zelen', 'redis', 'kabachok', 'tomaty'];
}
