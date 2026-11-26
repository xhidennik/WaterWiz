import io
import uuid

from PIL import Image, ImageOps

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _

from .models import WaterUser


def _validate_phone_digits(phone: str) -> None:
    # phone format: +<digits>
    if not phone or not phone.startswith("+"):
        raise ValidationError(_("Некорректный телефон."))
    digits = phone[1:]
    if len(digits) < 10 or len(digits) > 15:
        raise ValidationError(_("Некорректный телефон. Ожидаются 10–15 цифр."))


def _validate_text_max_len(value: str, max_len: int, field_name: str) -> None:
    if value is None:
        return
    if len(value) > max_len:
        raise ValidationError(_(f"{field_name} слишком длинный (макс. {max_len} символов)."))


class LoginForm(forms.Form):
    phone = forms.CharField(
        max_length=20,
        required=True,
        label="Телефон",
        widget=forms.TextInput(attrs={"class": "form-input", "id": "phone", "inputmode": "tel"}),
    )
    password = forms.CharField(
        required=True,
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-input", "id": "password"}),
    )

    def clean_phone(self) -> str:
        phone = WaterUser.objects.normalize_phone(self.cleaned_data["phone"])
        _validate_phone_digits(phone)
        return phone


class RegisterForm(forms.Form):
    phone = forms.CharField(
        max_length=20,
        required=True,
        label="Телефон",
        widget=forms.TextInput(attrs={"class": "form-input", "id": "reg_phone", "inputmode": "tel"}),
    )
    email = forms.EmailField(
        required=True,
        label="Почта",
        widget=forms.EmailInput(attrs={"class": "form-input", "id": "reg_email"}),
    )
    activity = forms.CharField(
        required=False,
        max_length=255,
        label="Активность",
        widget=forms.TextInput(attrs={"class": "form-input", "id": "reg_activity", "placeholder": "В сети"}),
    )
    about = forms.CharField(
        required=False,
        label="О себе",
        widget=forms.Textarea(attrs={"class": "form-textarea", "id": "reg_about", "rows": 4}),
    )
    password1 = forms.CharField(
        required=True,
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-input", "id": "reg_password1"}),
    )
    password2 = forms.CharField(
        required=True,
        label="Повтор пароля",
        widget=forms.PasswordInput(attrs={"class": "form-input", "id": "reg_password2"}),
    )

    def clean_phone(self) -> str:
        phone = WaterUser.objects.normalize_phone(self.cleaned_data["phone"])
        _validate_phone_digits(phone)
        return phone

    def clean_activity(self) -> str:
        value = (self.cleaned_data.get("activity") or "").strip()
        return value or "В сети"

    def clean_about(self) -> str:
        about = (self.cleaned_data.get("about") or "").strip()
        _validate_text_max_len(about, max_len=5000, field_name="О себе")
        return about

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get("phone")
        email = cleaned.get("email")
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")

        if phone and WaterUser.objects.filter(phone=phone).exists():
            self.add_error("phone", _("Пользователь с таким телефоном уже существует."))

        if email and WaterUser.objects.filter(email=email).exists():
            self.add_error("email", _("Пользователь с таким email уже существует."))

        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("Пароли не совпадают."))

        if phone and email and password1 and password1 == password2:
            # Server-side password validation per settings (AUTH_PASSWORD_VALIDATORS)
            tmp_user = WaterUser(phone=phone, email=email)
            validate_password(password1, tmp_user)

        return cleaned

    def save(self) -> WaterUser:
        phone = self.cleaned_data["phone"]
        email = self.cleaned_data["email"]
        password1 = self.cleaned_data["password1"]

        activity = self.cleaned_data.get("activity") or ""
        about = self.cleaned_data.get("about") or ""

        user = WaterUser.objects.create_user(
            phone=phone,
            email=email,
            password=password1,
            activity=activity,
            about=about,
            last_active_at=None,
        )
        return user


class ProfileForm(forms.Form):
    phone = forms.CharField(
        required=True,
        max_length=20,
        label="Телефон",
        widget=forms.TextInput(attrs={"class": "profile-edit-form__input", "id": "phone", "inputmode": "tel"}),
    )
    email = forms.EmailField(
        required=True,
        label="Почта",
        widget=forms.EmailInput(attrs={"class": "profile-edit-form__input", "id": "email"}),
    )
    name = forms.CharField(
        required=False,
        max_length=80,
        label="Имя",
        widget=forms.TextInput(attrs={"class": "profile-edit-form__input", "id": "name"}),
    )
    activity = forms.CharField(
        required=False,
        max_length=255,
        label="Активность",
        widget=forms.TextInput(attrs={"class": "profile-edit-form__input", "id": "activity"}),
    )
    about = forms.CharField(
        required=False,
        label="О себе",
        widget=forms.Textarea(
            attrs={
                "class": "profile-edit-form__textarea profile-edit-form__textarea--about",
                "id": "about",
                "rows": 3,
            }
        ),
    )

    avatar = forms.ImageField(
        required=False,
        label="Аватар",
        help_text="PNG/JPG, квадратное изображение будет обрезано до нужного размера.",
        widget=forms.ClearableFileInput(attrs={"id": "avatar", "accept": "image/*", "class": "form-input"}),
    )
    remove_avatar = forms.BooleanField(required=False, label="Удалить аватар")

    avatar_bg = forms.CharField(
        required=False,
        max_length=20,
        label="Цвет фона аватарки",
        widget=forms.TextInput(
            attrs={
                "class": "profile-edit-form__input",
                "id": "avatar_bg",
                "placeholder": "#2e7d32",
                "inputmode": "text",
            }
        ),
    )

    AVATAR_MAX_BYTES = 5 * 1024 * 1024
    AVATAR_SIZE = 256

    def clean_activity(self) -> str:
        return (self.cleaned_data.get("activity") or "").strip()

    def clean_name(self) -> str:
        return (self.cleaned_data.get("name") or "").strip()

    def clean_phone(self) -> str:
        phone = WaterUser.objects.normalize_phone(self.cleaned_data.get("phone") or "")
        _validate_phone_digits(phone)
        return phone

    def clean_email(self) -> str:
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_avatar_bg(self) -> str:
        val = (self.cleaned_data.get("avatar_bg") or "").strip()
        if not val:
            return ""
        if len(val) > 20:
            raise ValidationError(_("Некорректный цвет."))
        # allow: #rgb, #rrggbb, rgb(...), rgba(...), named colors.
        if val.startswith("#"):
            if len(val) not in (4, 7):
                raise ValidationError(_("Некорректный HEX-цвет."))
            import re as _re

            if not _re.fullmatch(r"#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}", val):
                raise ValidationError(_("Некорректный HEX-цвет."))
            return val
        if val.startswith("rgb(") or val.startswith("rgba("):
            import re as _re
            if not _re.fullmatch(r"rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(\s*,\s*(0|0?\.\d+|1(\.0+)?))?\s*\)", val):
                raise ValidationError(_("Некорректный RGB/RGBA цвет."))
        return val

    def clean_about(self) -> str:
        about = (self.cleaned_data.get("about") or "").strip()
        _validate_text_max_len(about, max_len=5000, field_name="О себе")
        return about

    def clean(self):
        cleaned = super().clean()
        user = getattr(self, "user_instance", None)
        phone = cleaned.get("phone")
        email = cleaned.get("email")
        if phone:
            qs = WaterUser.objects.filter(phone=phone)
            if user is not None:
                qs = qs.exclude(id=user.id)
            if qs.exists():
                self.add_error("phone", _("Пользователь с таким телефоном уже существует."))
        if email:
            qs = WaterUser.objects.filter(email=email)
            if user is not None:
                qs = qs.exclude(id=user.id)
            if qs.exists():
                self.add_error("email", _("Пользователь с таким email уже существует."))
        return cleaned

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if not avatar:
            return None

        if getattr(avatar, "size", 0) > self.AVATAR_MAX_BYTES:
            raise ValidationError(_(f"Аватар слишком большой (макс. {self.AVATAR_MAX_BYTES // (1024 * 1024)} МБ)."))

        # Ensure it's a readable image and preflight some sanity checks.
        try:
            img = Image.open(avatar)
            img.verify()
        except Exception:
            raise ValidationError(_("Файл не является корректным изображением."))

        # Rewind for later processing in save()
        try:
            avatar.seek(0)
        except Exception:
            pass
        return avatar

    def save(self, user: WaterUser) -> WaterUser:
        self.user_instance = user
        user.phone = self.cleaned_data.get("phone") or user.phone
        user.email = self.cleaned_data.get("email") or user.email
        user.name = self.cleaned_data.get("name") or ""
        user.activity = self.cleaned_data.get("activity") or ""
        user.about = self.cleaned_data.get("about") or ""
        user.avatar_bg = self.cleaned_data.get("avatar_bg") or ""

        remove_avatar = bool(self.cleaned_data.get("remove_avatar"))
        avatar = self.cleaned_data.get("avatar")

        if remove_avatar and user.avatar:
            old_avatar = user.avatar
            user.avatar = None
            old_avatar.delete(save=False)

        if avatar:
            # Replace existing file.
            if user.avatar:
                old_avatar = user.avatar
                user.avatar = None
                old_avatar.delete(save=False)

            # Crop to square and save as PNG (consistent raster output).
            img = Image.open(avatar)
            img = ImageOps.exif_transpose(img)
            img = ImageOps.fit(img, (self.AVATAR_SIZE, self.AVATAR_SIZE), method=Image.LANCZOS, centering=(0.5, 0.5))

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)

            file_name = f"avatar_{uuid.uuid4().hex}.png"
            user.avatar.save(file_name, ContentFile(buf.read()), save=False)

        user.save(update_fields=["phone", "email", "name", "activity", "about", "avatar_bg", "avatar"])
        return user

