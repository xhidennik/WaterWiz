from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
import re


class WaterUserManager(BaseUserManager):
    use_in_migrations = True

    def normalize_phone(self, value: str) -> str:
        """
        Нормализация телефона:
        - убираем пробелы/скобки/дефисы и любые нецифровые символы
        - приводим к виду +<digits> для стабильности unique-ключа
        """
        value = (value or "").strip()
        digits = re.sub(r"\D", "", value)
        if not digits:
            return ""
        return f"+{digits}"

    def create_user(self, phone, email, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone is required")
        if not email:
            raise ValueError("Email is required")

        phone = self.normalize_phone(phone)
        email = self.normalize_email(email)

        user = self.model(phone=phone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(phone, email, password=password, **extra_fields)


class WaterUser(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=20, unique=True, verbose_name="Телефон")
    email = models.EmailField(unique=True, verbose_name="Почта")

    name = models.CharField(max_length=80, blank=True, default="", verbose_name="Имя")

    # Вводится пользователем: статус/активность
    activity = models.CharField(max_length=255, blank=True, default="", verbose_name="Активность")

    # Вводится пользователем и редактируется
    about = models.TextField(blank=True, default="", verbose_name="О себе")

    # Нужное поле для админки и стандартных бэкендов авторизации
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_staff = models.BooleanField(default=False, verbose_name="Персонал")

    # Квадратный аватар, который обрезается при загрузке (см. forms.py)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True, verbose_name="Аватар")
    avatar_bg = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Цвет фона аватарки",
        help_text="CSS-цвет, например #2e7d32",
    )
    faceid_enabled = models.BooleanField(default=False, verbose_name="FaceID включен")

    last_active_at = models.DateTimeField(blank=True, null=True, verbose_name="Время последней активности")
    login_count = models.PositiveIntegerField(default=0, verbose_name="Количество входов")
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    objects = WaterUserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.email:
            local = self.email.split("@", 1)[0]
            if local:
                return local
        return self.phone

    @property
    def is_online(self) -> bool:
        if not self.last_active_at:
            return False
        return timezone.now() - self.last_active_at <= timedelta(minutes=5)


class FaceIDEmbedding(models.Model):
    user = models.ForeignKey(
        WaterUser,
        on_delete=models.CASCADE,
        related_name="faceid_embeddings",
        verbose_name="Пользователь",
    )
    embedding = models.BinaryField(verbose_name="Эмбеддинг лица")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Время создания")

    class Meta:
        verbose_name = "Эмбеддинг FaceID"
        verbose_name_plural = "Эмбеддинги FaceID"
        ordering = ["user", "created_at"]


class StorageItem(models.Model):
    CATEGORY_CHOICES = [
        ('inventory', 'Инвентарь'),
        ('products', 'Продукция'),
    ]
    STATUS_CHOICES = [
        ('in_stock', 'В наличии'),
        ('running_low', 'Заканчиваются'),
        ('reserved', 'Резерв'),
    ]

    name = models.CharField(max_length=200, verbose_name='Наименование')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    unit = models.CharField(max_length=20, verbose_name='Ед. изм.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock', verbose_name='Состояние')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='inventory', verbose_name='Категория')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Товар на складе'
        verbose_name_plural = 'Товары на складе'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"


class Location(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Локация")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Локация"
        verbose_name_plural = "Локации"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    class Status(models.TextChoices):
        pending = "pending", "Ожидает"
        in_progress = "in_progress", "В работе"
        done = "done", "Выполнено"

    class Priority(models.TextChoices):
        low = "low", "Низкий"
        medium = "medium", "Средний"
        high = "high", "Высокий"
        critical = "critical", "Критический"

    executor = models.ForeignKey(
        WaterUser,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Исполнитель",
    )
    title = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, default="", verbose_name="Описание")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="tasks", verbose_name="Локация")

    # Дата старта задачи (для отображения на календаре используем диапазон date..date+duration_days-1)
    date = models.DateField(verbose_name="Дата")
    duration_days = models.PositiveIntegerField(default=1, verbose_name="Кол-во дней на исполнение (дедлайн)")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.pending, verbose_name="Статус")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.low, verbose_name="Приоритетность")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"
        ordering = ["-date", "priority", "title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.date})"

    @staticmethod
    def filter_for_day(tasks, day):
        """
        Фильтрация задач по одному дню с учётом длительности.
        На sqlite/простых БД делаем вычисление на python, чтобы избежать сложных выражений.
        """
        day = day
        res = []
        for t in tasks:
            end_day = t.date + timedelta(days=max(0, (t.duration_days or 1) - 1))
            if t.date <= day <= end_day:
                res.append(t)
        return res