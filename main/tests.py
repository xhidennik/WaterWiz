from time import perf_counter

from django.conf import settings
from django.db import connections
from django.test import Client, TestCase
from django.urls import reverse

from .models import Location, StorageItem, Task
from .models import WaterUser


PAGES = [
    ("index", "main/index.html", "Управление тепличным комплексом"),
    ("about", "main/about.html", "О системе WaterWiz"),
    ("dashboard", "main/dashboard.html", "Дашборд - Тепличный комплекс"),
    ("storage", "main/storage.html", "Инвентарный склад"),
    ("water", "main/water.html", "Задачи и календарь"),
    ("adminpanel", "main/adminpanel.html", "Администрирование системы"),
    ("user", "main/user.html", "Личный кабинет"),
]


class AuthedBaseTestCase(TestCase):
    def setUp(self):
        self.user = WaterUser.objects.create_user(
            phone="+79990001122",
            email="test.user@example.com",
            password="TestPass123!",
            activity="В сети",
            about="Тестовый пользователь",
        )
        self.client.force_login(self.user)


class SmokeAndStatusTests(AuthedBaseTestCase):
    def test_smoke_and_status_200(self):
        for name, _, _ in PAGES:
            with self.subTest(page=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)


class TemplateFidelityTests(AuthedBaseTestCase):
    def test_templates_and_content_markers(self):
        for name, template, marker in PAGES:
            with self.subTest(page=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertTemplateUsed(response, template)
                self.assertContains(response, marker)


class SlowPagesTests(AuthedBaseTestCase):
    def test_slow_pages_under_threshold_ms(self):
        threshold_ms = int(getattr(settings, "SLOW_PAGE_THRESHOLD_MS", 500))
        self.assertGreater(threshold_ms, 0)

        for name, _, _ in PAGES:
            with self.subTest(page=name):
                url = reverse(name)
                # Warm-up request to reduce first-render noise.
                self.client.get(url)

                start = perf_counter()
                response = self.client.get(url)
                elapsed_ms = (perf_counter() - start) * 1000

                self.assertEqual(response.status_code, 200)
                self.assertLessEqual(
                    elapsed_ms,
                    threshold_ms,
                    msg=f"{name} is too slow: {elapsed_ms:.2f}ms > {threshold_ms}ms",
                )


class ConfigAvailabilityTests(TestCase):
    def test_required_settings_exist(self):
        # Security/config
        self.assertTrue(getattr(settings, "SECRET_KEY", None))
        self.assertIn("DATABASES", dir(settings))
        self.assertIsInstance(getattr(settings, "DEBUG", None), bool)

        # Database config
        self.assertIn("default", settings.DATABASES)
        default_db = settings.DATABASES["default"]
        self.assertIn("ENGINE", default_db)
        self.assertIn("NAME", default_db)
        self.assertTrue(default_db["NAME"])

        # Logging config
        logging_cfg = getattr(settings, "LOGGING", None)
        self.assertIsInstance(logging_cfg, dict)
        handlers = logging_cfg.get("handlers", {})
        for handler_key in ("server_file", "django_file", "errors_file"):
            self.assertIn(handler_key, handlers)
            filename = handlers[handler_key].get("filename")
            self.assertTrue(filename)
            self.assertIn("logs", str(filename))

        # Monitoring config
        threshold_ms = getattr(settings, "SLOW_PAGE_THRESHOLD_MS", None)
        self.assertIsNotNone(threshold_ms)
        self.assertGreaterEqual(int(threshold_ms), 1)


class DatabaseAvailabilityTests(TestCase):
    def test_database_connection_ok(self):
        conn = connections["default"]
        conn.ensure_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        self.assertIsNotNone(row)


class StorageDebilTests(AuthedBaseTestCase):
    def test_storage_filters_inventory_and_products(self):
        StorageItem.objects.create(
            name="Inventory Salt",
            quantity=10,
            unit="kg",
            status="in_stock",
            category="inventory",
        )
        StorageItem.objects.create(
            name="Product Tomato",
            quantity=5,
            unit="kg",
            status="running_low",
            category="products",
        )

        response = self.client.get(reverse("storage"))
        self.assertContains(response, "Inventory Salt")
        self.assertContains(response, "Product Tomato")
        self.assertContains(response, "В наличии")
        self.assertContains(response, "Заканчиваются")

    def test_storage_empty_messages_when_no_items(self):
        response = self.client.get(reverse("storage"))
        self.assertContains(response, "Нет товаров в этой категории.")
        self.assertContains(response, "Нет продукции.")


class ExtraSanityTests(TestCase):
    def test_unknown_url_returns_404(self):
        response = self.client.get("/this-url-should-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_redirect_to_login_when_not_authenticated(self):
        response = self.client.get(reverse("dashboard"))
        # Django default redirect code: 302
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_url_names_reverse_ok(self):
        # "Анти-дурак": убеждаемся, что именованные url существуют.
        for name, _, _ in PAGES:
            with self.subTest(name=name):
                url = reverse(name)
                self.assertTrue(url)


class TasksApiTests(AuthedBaseTestCase):
    def setUp(self):
        super().setUp()
        self.location = Location.objects.create(name="Тестовая локация")
        from datetime import date as _date

        self.start_date = _date(2026, 1, 1)

        # duration_days=3 => покрывает 2026-01-01, 2026-01-02, 2026-01-03
        self.task = Task.objects.create(
            executor=self.user,
            title="Тестовая задача",
            description="Описание задачи",
            location=self.location,
            date=self.start_date,
            duration_days=3,
            status="pending",
            priority="medium",
        )

    def test_api_tasks_get_filters_by_duration(self):
        url = reverse("api_tasks")

        resp_inside = self.client.get(url, {"date": "2026-01-03"})
        self.assertEqual(resp_inside.status_code, 200)
        data_inside = resp_inside.json()
        titles_inside = [t.get("title") for t in data_inside.get("tasks", [])]
        self.assertIn("Тестовая задача", titles_inside)

        resp_outside = self.client.get(url, {"date": "2026-01-04"})
        self.assertEqual(resp_outside.status_code, 200)
        data_outside = resp_outside.json()
        titles_outside = [t.get("title") for t in data_outside.get("tasks", [])]
        self.assertNotIn("Тестовая задача", titles_outside)

    def test_api_locations_get(self):
        url = reverse("api_locations")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = [l.get("name") for l in data.get("locations", [])]
        self.assertIn("Тестовая локация", names)


class StorageApiTests(AuthedBaseTestCase):
    def setUp(self):
        super().setUp()
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.item = StorageItem.objects.create(
            name="Семена",
            quantity=100,
            unit="уп",
            status="in_stock",
            category="inventory",
        )

    def test_api_storage_forbidden_for_non_staff(self):
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        resp = self.client.get(reverse("api_storage"))
        self.assertEqual(resp.status_code, 403)

    def test_api_storage_list_and_crud(self):
        list_resp = self.client.get(reverse("api_storage"), {"category": "inventory"})
        self.assertEqual(list_resp.status_code, 200)
        names = [i.get("name") for i in list_resp.json().get("items", [])]
        self.assertIn("Семена", names)

        create_resp = self.client.post(
            reverse("api_storage"),
            data='{"name":"Удобрение","quantity":5,"unit":"меш","status":"running_low","category":"inventory"}',
            content_type="application/json",
        )
        self.assertEqual(create_resp.status_code, 200)
        new_id = create_resp.json().get("item", {}).get("id")
        self.assertTrue(new_id)

        update_resp = self.client.put(
            reverse("api_storage_detail", kwargs={"item_id": new_id}),
            data='{"name":"Удобрение+","quantity":6,"unit":"меш","status":"in_stock","category":"inventory"}',
            content_type="application/json",
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json().get("item", {}).get("quantity"), 6)

        delete_resp = self.client.delete(reverse("api_storage_detail", kwargs={"item_id": new_id}))
        self.assertEqual(delete_resp.status_code, 200)
        self.assertFalse(StorageItem.objects.filter(id=new_id).exists())


class AdminMetricsApiTests(AuthedBaseTestCase):
    def test_metrics_forbidden_for_non_staff(self):
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        resp = self.client.get(reverse("api_admin_metrics"))
        self.assertEqual(resp.status_code, 403)

    def test_metrics_ok_for_staff(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        resp = self.client.get(reverse("api_admin_metrics"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("app_version", data)
        self.assertIn("db_ok", data)
        self.assertIn("log_entries", data)
        self.assertTrue(data["db_ok"])


class AdminPanelStorageTabTests(AuthedBaseTestCase):
    def test_storage_tab_visible_for_staff(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        resp = self.client.get(reverse("adminpanel"))
        self.assertContains(resp, 'data-tab="admin-storage"')
        self.assertContains(resp, "admin-storage.js")

    def test_storage_tab_hidden_for_regular_user(self):
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])
        resp = self.client.get(reverse("adminpanel"))
        self.assertNotContains(resp, 'data-tab="admin-storage"')
        self.assertNotContains(resp, "admin-storage.js")
