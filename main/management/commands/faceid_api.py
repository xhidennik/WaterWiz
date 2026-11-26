import json
import signal
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from faceid.api import FaceIDAPI
from faceid.system import FaceIDSystem
from faceid.utils import safe_log, setup_logging


class Command(BaseCommand):
    help = "Запускает FaceID API сервер (Flask) для обработки изображений лиц"

    def add_arguments(self, parser):
        parser.add_argument("--config", type=str, default="config.json",
                            help="Путь к конфигурационному файлу faceid")
        parser.add_argument("--port", type=int, default=0,
                            help="Порт для Flask API (переопределяет config)")

    def handle(self, *args, **options):
        config_path = Path(options["config"])
        if not config_path.exists():
            config_path = Path(__file__).resolve().parent.parent.parent.parent / "config.json"
        if not config_path.exists():
            self.stderr.write(self.style.ERROR(f"config.json not found at {options['config']}"))
            sys.exit(1)

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if options["port"]:
            config["web_api"]["port"] = options["port"]

        setup_logging(config)

        def signal_handler(sig, frame):
            safe_log("info", "Shutting down FaceID API...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.stdout.write(self.style.SUCCESS("Loading FaceID models..."))
        face_system = FaceIDSystem(config)
        self.stdout.write(self.style.SUCCESS(f"FaceID models loaded (device: {face_system.device})"))

        db_path = Path(config["database"]["path"]).resolve()
        self.stdout.write(self.style.WARNING(
            f"NOTE: facescan_db directory at {db_path} is NOT used "
            "in Django integration. Embeddings are stored in Django DB "
            "(FaceIDEmbedding model)."
        ))

        safe_log("info", f"FaceID API fully initialized. "
                 f"Device: {face_system.device}. "
                 f"DB (unused): {db_path}. "
                 f"Embeddings stored in Django FaceIDEmbedding model.")

        api = FaceIDAPI(face_system, config)
        host = config["web_api"]["host"]
        port = config["web_api"]["port"]
        self.stdout.write(self.style.SUCCESS(f"FaceID API starting on http://{host}:{port}"))
        safe_log("info", f"Listening on http://{host}:{port}")
        api.run()
