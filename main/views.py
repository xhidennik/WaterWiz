import base64
import logging
import struct
from datetime import timedelta

import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db.models import Count

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import FaceIDEmbedding, Location, StorageItem, Task, WaterUser
from .monitoring import collect_admin_metrics


logger = logging.getLogger("django")

FACEID_PENDING_SESSION_KEY = "faceid_pending_user_id"
FACEID_SETUP_SESSION_KEY = "faceid_prompt_setup_user_id"


def _strip_data_url(s: str) -> str:
    s = (s or "").strip()
    if "," in s:
        _, b64 = s.split(",", 1)
        return b64.strip()
    return s


def _extract_image_b64(request):
    if request.FILES.get("face_image"):
        try:
            raw = request.FILES["face_image"].read()
            return base64.b64encode(raw).decode("ascii")
        except Exception:
            return None

    return _strip_data_url(request.POST.get("captured_image_data"))


def _call_faceid(endpoint: str, image_b64: str) -> dict:
    url = f"{settings.FACEID_API_URL}/{endpoint}"
    try:
        resp = requests.post(url, json={"image": image_b64}, timeout=settings.FACEID_REQUEST_TIMEOUT)
        if not resp.ok:
            detail = resp.json().get("error", resp.reason)
            logger.error("FaceID API %s returned %s: %s", endpoint, resp.status_code, detail)
            return {"success": False, "face_detected": False, "message": f"FaceID API error: {detail}"}
        return resp.json()
    except requests.RequestException as e:
        logger.error("FaceID API %s connection failed: %s", endpoint, e)
        return {"success": False, "face_detected": False, "message": f"FaceID API connection failed: {e}"}


def _extract_embedding(image_b64: str):
    result = _call_faceid("extract", image_b64)
    if not result.get("success"):
        msg = result.get("message", "unknown")
        logger.warning("Embedding extraction failed: %s", msg)
        return None, msg
    emb_list = result.get("embedding")
    if not emb_list:
        logger.warning("FaceID API returned empty embedding list")
        return None, "FaceID API вернул пустой эмбеддинг"
    try:
        packed = struct.pack(f"{len(emb_list)}f", *emb_list)
    except struct.error as e:
        logger.error("struct.pack failed: %s", e)
        return None, f"Ошибка упаковки эмбеддинга: {e}"
    return packed, None


def _cosine_similarity(a: bytes, b: bytes) -> float:
    a = struct.unpack(f"{len(a)//4}f", a)
    b = struct.unpack(f"{len(b)//4}f", b)
    return sum(x * y for x, y in zip(a, b))


def _sync_faceid_state(user) -> None:
    """Согласовать флаг faceid_enabled с наличием эмбеддингов в БД."""
    has_emb = user.faceid_embeddings.exists()
    if has_emb and not user.faceid_enabled:
        user.faceid_enabled = True
        user.save(update_fields=["faceid_enabled"])
    elif not has_emb and user.faceid_enabled:
        user.faceid_enabled = False
        user.save(update_fields=["faceid_enabled"])


def _user_requires_faceid_verify(user) -> bool:
    _sync_faceid_state(user)
    return user.faceid_enabled and user.faceid_embeddings.exists()


def _compare_probe_to_user(user, image_b64: str | None) -> dict:
    threshold = settings.FACEID_SIMILARITY_THRESHOLD
    required_pct = round(threshold * 100, 1)
    if not image_b64:
        return {
            "passed": False,
            "similarity_pct": None,
            "missing_pct": None,
            "required_pct": required_pct,
            "error_msg": "Не удалось получить изображение. Сделайте снимок с камеры или загрузите файл.",
        }
    probe_emb, err = _extract_embedding(image_b64)
    if probe_emb is None:
        return {
            "passed": False,
            "similarity_pct": None,
            "missing_pct": None,
            "required_pct": required_pct,
            "error_msg": f"Не удалось обработать фото. {err or 'Убедитесь, что лицо видно.'}",
        }
    stored_embs = list(user.faceid_embeddings.values_list("embedding", flat=True))
    similarities = [_cosine_similarity(probe_emb, s) for s in stored_embs]
    best = max(similarities) if similarities else 0.0
    similarity_pct = round(best * 100, 1)
    passed = best >= threshold
    missing_pct = None if passed else round(max(0.0, required_pct - similarity_pct), 1)
    error_msg = ""
    if not passed:
        error_msg = (
            f"FaceID не совпал: нужно минимум {required_pct}%, "
            f"текущее фото дало {similarity_pct}%"
            + (f" (не хватает {missing_pct}%)." if missing_pct is not None else ".")
        )
    return {
        "passed": passed,
        "best": best,
        "similarity_pct": similarity_pct,
        "missing_pct": missing_pct,
        "required_pct": required_pct,
        "error_msg": error_msg,
    }


def _collect_setup_images_b64(request) -> list[str]:
    images = []
    for raw in request.POST.getlist("captured_images[]"):
        clean = _strip_data_url(raw)
        if clean:
            images.append(clean)
    if not images:
        single = _extract_image_b64(request)
        if single:
            images.append(single)
    return images


def index(request):
    return render(request, "main/index.html")


def about(request):
    return render(request, "main/about.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    login_form = LoginForm()
    register_form = RegisterForm(initial={"activity": "В сети"})

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "login":
            login_form = LoginForm(request.POST)
            # Keep register form clean, чтобы не показывать ошибки "не того" блока.
            register_form = RegisterForm(initial={"activity": "В сети"})
            if login_form.is_valid():
                phone = login_form.cleaned_data["phone"]
                password = login_form.cleaned_data["password"]
                user = authenticate(request, phone=phone, password=password)
                if user is None:
                    login_form.add_error(None, "Неверный телефон или пароль.")
                else:
                    if _user_requires_faceid_verify(user):
                        logger.info("login faceid_required user=%s -> redirect verify", user.phone)
                        request.session[FACEID_PENDING_SESSION_KEY] = user.id
                        return redirect("faceid_verify")
                    logger.info("login OK user=%s (faceid not required)", user.phone)
                    user.last_active_at = timezone.now()
                    user.login_count = (user.login_count or 0) + 1
                    user.save(update_fields=["last_active_at", "login_count"])
                    auth_login(request, user)
                    return redirect("dashboard")

        elif action == "register":
            register_form = RegisterForm(request.POST, initial={"activity": "В сети"})
            login_form = LoginForm()
            if register_form.is_valid():
                user = register_form.save()
                logger.info("register OK user=%s -> redirect faceid_setup", user.phone)
                user.last_active_at = timezone.now()
                user.login_count = (user.login_count or 0) + 1
                user.save(update_fields=["login_count", "last_active_at"])
                auth_login(request, user)
                request.session[FACEID_SETUP_SESSION_KEY] = user.id
                return redirect("faceid_setup")

        else:
            login_form.add_error(None, "Неизвестное действие формы.")

    return render(
        request,
        "main/login.html",
        {
            "login_form": login_form,
            "register_form": register_form,
        },
    )


@login_required
def faceid_setup(request):
    prompt_user_id = request.session.get(FACEID_SETUP_SESSION_KEY)
    if prompt_user_id and prompt_user_id != request.user.id:
        request.session.pop(FACEID_SETUP_SESSION_KEY, None)

    logger.info("faceid_setup GET user=%s", request.user.phone)

    error_msg = ""
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        logger.info("faceid_setup POST action=%s user=%s", action, request.user.phone)

        if action == "skip":
            request.session.pop(FACEID_SETUP_SESSION_KEY, None)
            logger.info("faceid_setup skipped for user=%s", request.user.phone)
            return redirect("dashboard")
        if action == "enable":
            images_b64 = _collect_setup_images_b64(request)
            logger.info("faceid_setup received %d images from user=%s", len(images_b64), request.user.phone)

            if not images_b64:
                error_msg = "Не удалось получить изображения. Включите камеру (3 снимка) или загрузите фото."
                logger.warning("faceid_setup no images from user=%s", request.user.phone)
            else:
                old_count = request.user.faceid_embeddings.count()
                if old_count:
                    request.user.faceid_embeddings.all().delete()
                    logger.info("faceid_setup cleared %d old embeddings for user=%s", old_count, request.user.phone)
                saved = 0
                errors = []
                for i, clean in enumerate(images_b64):
                    emb, err = _extract_embedding(clean)
                    if emb is not None:
                        FaceIDEmbedding.objects.create(user=request.user, embedding=emb)
                        saved += 1
                        logger.info("faceid_setup image %d OK -> embedding saved (%d bytes)", i, len(emb))
                    else:
                        logger.error("faceid_setup image %d FAILED: %s", i, err)
                        errors.append(err or "неизвестная ошибка")
                if saved == 0:
                    error_msg = "Не удалось обработать ни одного снимка."
                    if errors:
                        error_msg += " Подробнее: " + "; ".join(errors)
                    logger.error("faceid_setup ALL %d images failed for user=%s: %s",
                                 len(images_b64), request.user.phone, error_msg)
                    request.session.pop(FACEID_SETUP_SESSION_KEY, None)
                else:
                    request.user.faceid_enabled = True
                    request.user.save(update_fields=["faceid_enabled"])
                    logger.info("faceid_setup SUCCESS for user=%s: %d/%d embeddings saved",
                                request.user.phone, saved, len(images_b64))
                    request.session.pop(FACEID_SETUP_SESSION_KEY, None)
                    return redirect("dashboard")
    return render(request, "main/faceid_setup.html", {"error_msg": error_msg})


def faceid_verify(request):
    pending_user_id = request.session.get(FACEID_PENDING_SESSION_KEY)
    if not pending_user_id:
        logger.warning("faceid_verify no pending user in session")
        return redirect("login")
    user = WaterUser.objects.filter(id=pending_user_id, is_active=True).first()
    if not user or not _user_requires_faceid_verify(user):
        logger.warning("faceid_verify user=%s not found or faceid not configured", pending_user_id)
        request.session.pop(FACEID_PENDING_SESSION_KEY, None)
        return redirect("login")

    logger.info("faceid_verify GET pending_user=%s emb_count=%d",
                user.phone, user.faceid_embeddings.count())

    error_msg = ""
    similarity_pct = None
    required_pct = round(settings.FACEID_SIMILARITY_THRESHOLD * 100, 1)
    missing_pct = None
    if request.method == "POST":
        image_b64 = _extract_image_b64(request)
        logger.info("faceid_verify POST user=%s image_b64_len=%s",
                    user.phone, len(image_b64) if image_b64 else "None")
        result = _compare_probe_to_user(user, image_b64)
        similarity_pct = result["similarity_pct"]
        missing_pct = result["missing_pct"]
        required_pct = result["required_pct"]
        if result.get("best") is not None:
            logger.info("faceid_verify user=%s best_sim=%.4f", user.phone, result["best"])
        if result["passed"]:
            user.last_active_at = timezone.now()
            user.login_count = (user.login_count or 0) + 1
            user.save(update_fields=["last_active_at", "login_count"])
            auth_login(request, user)
            logger.info("faceid_verify GRANTED user=%s sim=%.4f", user.phone, result["best"])
            request.session.pop(FACEID_PENDING_SESSION_KEY, None)
            return redirect("dashboard")
        error_msg = result["error_msg"]
        if result.get("best") is not None:
            logger.warning("faceid_verify DENIED user=%s sim=%.4f < %.2f",
                           user.phone, result["best"], settings.FACEID_SIMILARITY_THRESHOLD)

    return render(
        request,
        "main/faceid_verify.html",
        {
            "error_msg": error_msg,
            "phone": user.phone,
            "required_pct": required_pct,
            "similarity_pct": similarity_pct,
            "missing_pct": missing_pct,
        },
    )


@login_required
def faceid_test(request):
    """Быстрая проверка FaceID без выхода из аккаунта."""
    _sync_faceid_state(request.user)
    if not request.user.faceid_embeddings.exists():
        messages.warning(request, "Сначала настройте FaceID — сохраните снимки лица.")
        return redirect(reverse("user") + "?tab=user-edit")

    error_msg = ""
    success_msg = ""
    similarity_pct = None
    missing_pct = None
    required_pct = round(settings.FACEID_SIMILARITY_THRESHOLD * 100, 1)

    if request.method == "POST":
        image_b64 = _extract_image_b64(request)
        logger.info("faceid_test POST user=%s image_b64_len=%s",
                    request.user.phone, len(image_b64) if image_b64 else "None")
        result = _compare_probe_to_user(request.user, image_b64)
        similarity_pct = result["similarity_pct"]
        missing_pct = result["missing_pct"]
        required_pct = result["required_pct"]
        if result["passed"]:
            success_msg = f"Лицо совпало: {similarity_pct}% (порог {required_pct}%)."
            logger.info("faceid_test OK user=%s sim=%.4f", request.user.phone, result.get("best"))
        else:
            error_msg = result["error_msg"]
            logger.warning("faceid_test FAIL user=%s: %s", request.user.phone, error_msg)

    return render(
        request,
        "main/faceid_test.html",
        {
            "error_msg": error_msg,
            "success_msg": success_msg,
            "required_pct": required_pct,
            "similarity_pct": similarity_pct,
            "missing_pct": missing_pct,
            "emb_count": request.user.faceid_embeddings.count(),
        },
    )


@login_required
def dashboard(request):
    request.user.last_active_at = timezone.now()
    request.user.save(update_fields=["last_active_at"])
    return render(request, "main/dashboard.html")


@login_required
def storage(request):
    request.user.last_active_at = timezone.now()
    request.user.save(update_fields=["last_active_at"])
    inventory_items = StorageItem.objects.filter(category="inventory")
    products_items = StorageItem.objects.filter(category="products")
    return render(
        request,
        "main/storage.html",
        {
            "inventory_items": inventory_items,
            "products_items": products_items,
        },
    )


@login_required
def water(request):
    request.user.last_active_at = timezone.now()
    request.user.save(update_fields=["last_active_at"])
    return render(request, "main/water.html")


@login_required
def adminpanel(request):
    request.user.last_active_at = timezone.now()
    request.user.save(update_fields=["last_active_at"])
    staff_users = (
        WaterUser.objects.filter(is_active=True, is_staff=True)
        .order_by("name", "email", "phone")
    )
    all_users = (
        WaterUser.objects.filter(is_active=True)
        .annotate(tasks_count=Count("tasks"))
        .order_by("-is_staff", "name", "email", "phone")
    )
    return render(
        request,
        "main/adminpanel.html",
        {
            "staff_users": staff_users,
            "all_users": all_users,
            "can_manage_storage": request.user.is_staff,
        },
    )


@login_required
def user(request):
    _sync_faceid_state(request.user)
    active_tab = request.GET.get("tab") or "user-profile"
    profile_saved = request.GET.get("saved") == "1"

    if request.method == "POST":
        active_tab = "user-edit"
        if request.POST.get("action") == "disable_faceid":
            count = request.user.faceid_embeddings.count()
            request.user.faceid_embeddings.all().delete()
            request.user.faceid_enabled = False
            request.user.save(update_fields=["faceid_enabled"])
            request.user.last_active_at = timezone.now()
            request.user.save(update_fields=["last_active_at"])
            logger.info("faceid DISABLED user=%s (%d embeddings deleted)", request.user.phone, count)
            return redirect(reverse("user") + "?tab=user-edit")

        form = ProfileForm(request.POST, request.FILES)
        form.user_instance = request.user
        if form.is_valid():
            form.save(request.user)
            request.user.last_active_at = timezone.now()
            request.user.save(update_fields=["last_active_at"])
            return redirect(reverse("user") + "?tab=user-edit&saved=1")
    else:
        form = ProfileForm(
            initial={
                "phone": request.user.phone,
                "email": request.user.email,
                "name": request.user.name,
                "activity": request.user.activity,
                "about": request.user.about,
                "avatar_bg": request.user.avatar_bg,
            }
        )

    if active_tab not in ("user-profile", "user-tasks", "user-edit"):
        active_tab = "user-profile"

    base_tasks_qs = (
        Task.objects.filter(executor=request.user)
        .select_related("location")
        .order_by("-date", "-priority", "title")
    )
    current_tasks = base_tasks_qs.exclude(status=Task.Status.done)[:100]
    user_tasks = base_tasks_qs[:50]
    return render(
        request,
        "main/user.html",
        {
            "form": form,
            "user_tasks": user_tasks,
            "current_tasks": current_tasks,
            "active_tab": active_tab,
            "profile_saved": profile_saved,
        },
    )


@login_required
def logout_view(request):
    auth_logout(request)
    return redirect("index")


def _parse_date(value: str):
    # expected: YYYY-MM-DD
    try:
        parts = value.split("-")
        if len(parts) != 3:
            return None
        year, month, day = map(int, parts)
        import datetime as _dt

        return _dt.date(year, month, day)
    except Exception:
        return None


@login_required
@require_http_methods(["GET"])
def api_admin_metrics(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Forbidden")
    return JsonResponse(collect_admin_metrics())


@login_required
@require_http_methods(["GET"])
def api_locations(request):
    locations = Location.objects.all().order_by("name").values("id", "name")
    return JsonResponse({"locations": list(locations)})


@login_required
@require_http_methods(["GET"])
def api_users(request):
    qs = WaterUser.objects.filter(is_active=True).order_by("-is_staff", "email", "phone")
    users = []
    if request.user.is_authenticated:
        users.append({"id": request.user.id, "display_name": request.user.display_name, "is_staff": bool(request.user.is_staff)})
    for u in qs:
        if request.user.is_authenticated and u.id == request.user.id:
            continue
        users.append({"id": u.id, "display_name": u.display_name, "is_staff": bool(u.is_staff)})
    return JsonResponse({"users": users})


@login_required
def api_tasks(request):
    """
    GET  /api/tasks/?date=YYYY-MM-DD&location_id=optional
    POST /api/tasks/  { "tasks": [ ... ] } (bulk create) or { ... } single create
    """
    if request.method == "GET":
        date_str = request.GET.get("date") or ""
        day = _parse_date(date_str)
        if not day:
            return HttpResponseBadRequest("Invalid date")

        location_id = request.GET.get("location_id")
        executor_id = request.GET.get("executor_id")
        executor = request.user
        if request.user.is_staff and executor_id:
            executor = WaterUser.objects.filter(id=executor_id, is_active=True).first() or request.user
        base_qs = (
            Task.objects.filter(executor=executor)
            .select_related("location")
            .filter(date__lte=day)
            .order_by("-date", "-priority", "title")
        )

        tasks_for_day = []
        for t in base_qs:
            end_day = t.date + timedelta(days=max(0, (t.duration_days or 1) - 1))
            if t.date <= day <= end_day:
                if location_id and str(t.location_id) != str(location_id):
                    continue
                tasks_for_day.append(
                    {
                        "id": t.id,
                        "date": t.date.isoformat(),
                        "executor": t.executor.display_name,
                        "executor_id": t.executor_id,
                        "title": t.title,
                        "description": t.description,
                        "location": {"id": t.location_id, "name": t.location.name},
                        "duration_days": t.duration_days,
                        "status": t.status,
                        "priority": t.priority,
                        "deadline_date": (t.date + timedelta(days=max(0, (t.duration_days or 1) - 1))).isoformat(),
                    }
                )

        return JsonResponse({"tasks": tasks_for_day})

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")

        tasks_payload = payload.get("tasks")
        if tasks_payload is None:
            tasks_payload = [payload]

        created_ids = []
        for item in tasks_payload:
            date = _parse_date(item.get("date") or "")
            if not date:
                return HttpResponseBadRequest("Missing/invalid date")

            location_id = item.get("location_id")
            if not location_id:
                return HttpResponseBadRequest("Missing location_id")

            location = Location.objects.filter(id=location_id).first()
            if not location:
                return HttpResponseBadRequest("Unknown location_id")

            title = (item.get("title") or "").strip()
            if not title or len(title) > 200:
                return HttpResponseBadRequest("Invalid title")

            description = (item.get("description") or "").strip()
            duration_days = int(item.get("duration_days") or 1)
            if duration_days < 1 or duration_days > 365:
                return HttpResponseBadRequest("Invalid duration_days")

            status = item.get("status") or Task.Status.pending
            priority = item.get("priority") or Task.Priority.low
            status_values = {c.value for c in Task.Status}
            priority_values = {c.value for c in Task.Priority}
            if status not in status_values:
                return HttpResponseBadRequest("Invalid status")
            if priority not in priority_values:
                return HttpResponseBadRequest("Invalid priority")

            executor = request.user
            executor_id = item.get("executor_id")
            if request.user.is_staff and executor_id:
                executor = WaterUser.objects.filter(id=executor_id, is_active=True).first()
                if not executor:
                    return HttpResponseBadRequest("Unknown executor_id")

            t = Task.objects.create(
                executor=executor,
                title=title,
                description=description,
                location=location,
                date=date,
                duration_days=duration_days,
                status=status,
                priority=priority,
            )
            created_ids.append(t.id)

        return JsonResponse({"created_ids": created_ids, "count": len(created_ids)})

    return HttpResponseNotAllowed(["GET", "POST"])


@login_required
def api_task_detail(request, task_id: int):
    """
    PUT    /api/tasks/<id>  (update)
    DELETE /api/tasks/<id>  (delete)
    """
    try:
        qs = Task.objects.select_related("location", "executor").filter(id=task_id)
        if not request.user.is_staff:
            qs = qs.filter(executor=request.user)
        task = qs.get()
    except Task.DoesNotExist:
        return HttpResponseBadRequest("Task not found")

    if request.method == "DELETE":
        task.delete()
        return JsonResponse({"deleted": True})

    if request.method == "PUT":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")

        date = _parse_date(payload.get("date") or task.date.isoformat())
        if not date:
            return HttpResponseBadRequest("Invalid date")

        location_id = payload.get("location_id") or task.location_id
        location = Location.objects.filter(id=location_id).first()
        if not location:
            return HttpResponseBadRequest("Unknown location_id")

        title = (payload.get("title") or task.title).strip()
        if not title or len(title) > 200:
            return HttpResponseBadRequest("Invalid title")

        description = (payload.get("description") or task.description or "").strip()
        duration_days = int(payload.get("duration_days") or task.duration_days or 1)
        if duration_days < 1 or duration_days > 365:
            return HttpResponseBadRequest("Invalid duration_days")

        status = payload.get("status") or task.status
        priority = payload.get("priority") or task.priority
        status_values = {c.value for c in Task.Status}
        priority_values = {c.value for c in Task.Priority}
        if status not in status_values:
            return HttpResponseBadRequest("Invalid status")
        if priority not in priority_values:
            return HttpResponseBadRequest("Invalid priority")

        task.date = date
        task.location = location
        task.title = title
        task.description = description
        task.duration_days = duration_days
        task.status = status
        task.priority = priority

        if request.user.is_staff and payload.get("executor_id"):
            executor = WaterUser.objects.filter(id=payload.get("executor_id"), is_active=True).first()
            if not executor:
                return HttpResponseBadRequest("Unknown executor_id")
            task.executor = executor
            task.save(update_fields=["date", "location", "executor", "title", "description", "duration_days", "status", "priority"])
        else:
            task.save(update_fields=["date", "location", "title", "description", "duration_days", "status", "priority"])

        return JsonResponse({"updated": True, "id": task.id})

    return HttpResponseNotAllowed(["PUT", "DELETE"])


def _storage_item_json(item: StorageItem) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": item.quantity,
        "unit": item.unit,
        "status": item.status,
        "category": item.category,
    }


def _parse_storage_payload(payload: dict, *, require_category: bool = False):
    name = (payload.get("name") or "").strip()
    if not name or len(name) > 200:
        return None, HttpResponseBadRequest("Invalid name")

    try:
        quantity = int(payload.get("quantity"))
    except (TypeError, ValueError):
        return None, HttpResponseBadRequest("Invalid quantity")
    if quantity < 1 or quantity > 10_000_000:
        return None, HttpResponseBadRequest("Invalid quantity")

    unit = (payload.get("unit") or "").strip()
    if not unit or len(unit) > 20:
        return None, HttpResponseBadRequest("Invalid unit")

    status = payload.get("status") or StorageItem.STATUS_CHOICES[0][0]
    status_values = {c[0] for c in StorageItem.STATUS_CHOICES}
    if status not in status_values:
        return None, HttpResponseBadRequest("Invalid status")

    category = payload.get("category")
    if require_category:
        category_values = {c[0] for c in StorageItem.CATEGORY_CHOICES}
        if category not in category_values:
            return None, HttpResponseBadRequest("Invalid category")
    elif category is not None:
        category_values = {c[0] for c in StorageItem.CATEGORY_CHOICES}
        if category not in category_values:
            return None, HttpResponseBadRequest("Invalid category")

    data = {"name": name, "quantity": quantity, "unit": unit, "status": status}
    if category is not None:
        data["category"] = category
    return data, None


@login_required
def api_storage(request):
    """
    GET  /api/storage/?category=inventory|products
    POST /api/storage/  (staff only)
    """
    if not request.user.is_staff:
        return HttpResponseForbidden("Forbidden")

    if request.method == "GET":
        category = (request.GET.get("category") or "").strip()
        qs = StorageItem.objects.all().order_by("name")
        if category:
            if category not in {c[0] for c in StorageItem.CATEGORY_CHOICES}:
                return HttpResponseBadRequest("Invalid category")
            qs = qs.filter(category=category)
        items = [_storage_item_json(i) for i in qs]
        return JsonResponse({"items": items})

    if request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")

        data, err = _parse_storage_payload(payload, require_category=True)
        if err:
            return err

        item = StorageItem.objects.create(**data)
        return JsonResponse({"created": True, "item": _storage_item_json(item)})

    return HttpResponseNotAllowed(["GET", "POST"])


@login_required
def api_storage_detail(request, item_id: int):
    """
    PUT    /api/storage/<id>/
    DELETE /api/storage/<id>/
    """
    if not request.user.is_staff:
        return HttpResponseForbidden("Forbidden")

    try:
        item = StorageItem.objects.get(id=item_id)
    except StorageItem.DoesNotExist:
        return HttpResponseBadRequest("Item not found")

    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"deleted": True})

    if request.method == "PUT":
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return HttpResponseBadRequest("Invalid JSON")

        merged = {
            "name": payload.get("name", item.name),
            "quantity": payload.get("quantity", item.quantity),
            "unit": payload.get("unit", item.unit),
            "status": payload.get("status", item.status),
            "category": payload.get("category", item.category),
        }
        data, err = _parse_storage_payload(merged, require_category=True)
        if err:
            return err

        item.name = data["name"]
        item.quantity = data["quantity"]
        item.unit = data["unit"]
        item.status = data["status"]
        item.category = data["category"]
        item.save(update_fields=["name", "quantity", "unit", "status", "category", "updated_at"])
        return JsonResponse({"updated": True, "item": _storage_item_json(item)})

    return HttpResponseNotAllowed(["PUT", "DELETE"])