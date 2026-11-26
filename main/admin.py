from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import FaceIDEmbedding, Location, StorageItem, Task, WaterUser

@admin.register(StorageItem)
class StorageItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'quantity', 'unit', 'status', 'created_at')
    list_filter = ('status', 'category', 'unit')  # фильтры справа
    search_fields = ('name',)
    list_editable = ('quantity', 'status')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (_("Основное"), {"fields": ("name", "category", "quantity", "unit", "status")}),
        (_("Время"), {"fields": ("created_at", "updated_at")}),
    )


@admin.register(WaterUser)
class WaterUserAdmin(admin.ModelAdmin):
    list_display = (
        "avatar_thumb",
        "phone",
        "email",
        "activity",
        "last_active_at",
        "login_count",
        "is_active",
        "is_staff",
    )
    list_filter = ("is_active", "is_staff", "last_active_at")
    search_fields = ("phone", "email", "activity")
    ordering = ("-last_active_at", "phone")
    readonly_fields = ("date_joined", "last_login")

    fieldsets = (
        (_("Контакты"), {"fields": ("phone", "email", "avatar")}),
        (_("О себе"), {"fields": ("activity", "about")}),
        (_("Статус"), {"fields": ("is_active", "is_staff")}),
        (_("Активность"), {"fields": ("last_active_at", "login_count")}),
        (
            _("Права"),
            {
                "fields": (
                    "groups",
                    "user_permissions",
                    "is_superuser",
                )
            },
        ),
        (_("Системное"), {"fields": ("date_joined", "last_login")}),
    )

    def avatar_thumb(self, obj: WaterUser):
        if not obj.avatar:
            return ""
        return format_html(
            '<img src="{}" alt="{}" style="width:42px;height:42px;object-fit:cover;border-radius:12px;" />',
            obj.avatar.url,
            "Аватар",
        )

    avatar_thumb.short_description = _("Аватар")
    avatar_thumb.allow_tags = True


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at",)

    fieldsets = (
        (_("Основное"), {"fields": ("name",)}),
        (_("Время"), {"fields": ("created_at",)}),
    )


@admin.register(FaceIDEmbedding)
class FaceIDEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__phone", "user__email")
    ordering = ("-created_at",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "executor",
        "date",
        "duration_days",
        "location",
        "status",
        "priority",
        "updated_at",
    )
    list_filter = ("status", "priority", "location", "date", "executor")
    search_fields = ("title", "description")
    ordering = ("-date", "-updated_at", "title")
    date_hierarchy = "date"

    fieldsets = (
        (_("Основное"), {"fields": ("executor", "title", "description", "location")}),
        (_("Планирование"), {"fields": ("date", "duration_days")}),
        (_("Состояние"), {"fields": ("status", "priority")}),
        (_("Время"), {"fields": ("created_at", "updated_at")}),
    )