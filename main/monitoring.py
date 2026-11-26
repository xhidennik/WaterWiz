"""Сбор реальных метрик для вкладки «Системный мониторинг»."""

from __future__ import annotations

import platform
import re
import shutil
import socket
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import connection
from django.utils import timezone

import django

from .middleware import requests_per_minute
from .models import WaterUser

try:
    import psutil
except ImportError:
    psutil = None

_LOG_LINE_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (?P<level>[A-Z]+) \| (?P<msg>.+)$"
)


def _gb(value_bytes: int) -> float:
    return round(value_bytes / (1024**3), 1)


def _format_gb(value_gb: float) -> str:
    if value_gb >= 1024:
        return f"{value_gb / 1024:.1f} ТБ"
    return f"{value_gb:.1f} ГБ"


def get_app_version() -> str:
    pyproject = Path(settings.BASE_DIR) / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if match:
            return f"WaterWiz v{match.group(1)}"
    except OSError:
        pass
    return "WaterWiz"


def check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


def get_db_backup_mtime() -> str | None:
    try:
        db_name = settings.DATABASES["default"]["NAME"]
        path = Path(db_name)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            return mtime.strftime("%d.%m.%Y %H:%M")
    except Exception:
        pass
    return None


def _psutil_metrics() -> dict:
    if psutil is None:
        return {
            "ram_percent": None,
            "cpu_percent": None,
            "ram_total_gb": None,
            "cpu_count": None,
            "uptime_seconds": None,
            "disks": [],
        }

    vm = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=None)
    if cpu_percent == 0.0:
        cpu_percent = psutil.cpu_percent(interval=0.1)

    disks = []
    seen = set()
    for part in psutil.disk_partitions(all=False):
        mount = part.mountpoint
        if mount in seen:
            continue
        seen.add(mount)
        try:
            usage = psutil.disk_usage(mount)
        except (PermissionError, OSError):
            continue
        total_gb = _gb(usage.total)
        used_gb = _gb(usage.used)
        percent = usage.percent if usage.percent else round(used_gb / total_gb * 100, 1) if total_gb else 0
        label = mount
        if mount == "/" or mount.lower() == "c:\\":
            label = f"Системный ({mount})"
        disks.append(
            {
                "name": label,
                "mount": mount,
                "total_gb": total_gb,
                "used_gb": used_gb,
                "percent": round(float(percent), 1),
            }
        )
        if len(disks) >= 4:
            break

    if not disks:
        project_path = Path(settings.BASE_DIR)
        usage = shutil.disk_usage(project_path)
        total_gb = _gb(usage.total)
        used_gb = _gb(usage.used)
        percent = round(used_gb / total_gb * 100, 1) if total_gb else 0
        disks.append(
            {
                "name": "Диск проекта",
                "mount": str(project_path),
                "total_gb": total_gb,
                "used_gb": used_gb,
                "percent": percent,
            }
        )

    return {
        "ram_percent": round(vm.percent, 1),
        "cpu_percent": round(float(cpu_percent), 1),
        "ram_total_gb": _gb(vm.total),
        "cpu_count": psutil.cpu_count(logical=True) or 0,
        "uptime_seconds": int(timezone.now().timestamp() - psutil.boot_time()),
        "disks": disks,
    }


def _parse_log_level(level_name: str) -> str:
    level = (level_name or "").upper()
    if level in ("CRITICAL", "FATAL"):
        return "critical"
    if level == "ERROR":
        return "error"
    if level in ("WARNING", "WARN"):
        return "warning"
    if level == "DEBUG":
        return "info"
    return "success" if level == "SUCCESS" else "info"


def tail_log_file(path: Path, max_lines: int = 20) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 65536))
            chunk = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []

    entries = []
    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _LOG_LINE_RE.match(line)
        if match:
            time_short = match.group("time").split(" ", 1)[-1]
            entries.append(
                {
                    "time": time_short,
                    "msg": match.group("msg"),
                    "level": _parse_log_level(match.group("level")),
                }
            )
        else:
            entries.append({"time": "", "msg": line, "level": "info"})
    return entries[-max_lines:]


def collect_log_entries() -> list[dict]:
    files = [
        getattr(settings, "ERRORS_LOG_FILE", None),
        getattr(settings, "DJANGO_LOG_FILE", None),
        getattr(settings, "SERVER_LOG_FILE", None),
    ]
    combined: list[dict] = []
    seen = set()
    for file_path in files:
        if not file_path:
            continue
        path = Path(file_path)
        for entry in tail_log_file(path, max_lines=15):
            key = (entry.get("time"), entry.get("msg"))
            if key in seen:
                continue
            seen.add(key)
            combined.append(entry)
    return combined[-40:]


def collect_admin_metrics() -> dict:
    ps = _psutil_metrics()
    db_ok = check_database()
    online_users = WaterUser.objects.filter(
        is_active=True,
        last_active_at__gte=timezone.now() - timedelta(minutes=5),
    ).count()
    try:
        active_sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()
    except Exception:
        active_sessions = 0

    status_text = "Работает стабильно" if db_ok else "Ошибка базы данных"
    status_class = "ok" if db_ok else "error"

    backup = get_db_backup_mtime()
    primary_disk = ps["disks"][0] if ps["disks"] else None

    return {
        "app_version": get_app_version(),
        "django_version": django.get_version(),
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}".strip(),
        "db_ok": db_ok,
        "status_text": status_text,
        "status_class": status_class,
        "ram_percent": ps["ram_percent"],
        "cpu_percent": ps["cpu_percent"],
        "ram_total_gb": ps["ram_total_gb"],
        "cpu_count": ps["cpu_count"],
        "uptime_seconds": ps["uptime_seconds"],
        "disks": ps["disks"],
        "disk_total_gb": primary_disk["total_gb"] if primary_disk else None,
        "active_sessions": active_sessions,
        "online_users": online_users,
        "requests_per_minute": requests_per_minute(),
        "db_backup_at": backup,
        "log_entries": collect_log_entries(),
        "psutil_available": psutil is not None,
    }
