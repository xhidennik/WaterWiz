import json
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Dict

from faceid.api import FaceIDAPI
from faceid.cli import run_menu
from faceid.system import FaceIDSystem
from faceid.utils import safe_log, self_test, setup_logging


def load_config(path: Path = Path("config.json")) -> Dict[str, Any]:
    # Try cwd first, then facescan/config.json for convenience.
    candidates = [path, Path(__file__).resolve().parent / "config.json"]
    cfg_path = next((p for p in candidates if p.exists()), None)
    if cfg_path is None:
        raise FileNotFoundError("config.json not found (checked project root and facescan/)")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    config = load_config()
    setup_logging(config)

    def signal_handler(sig, frame):
        safe_log("info", "Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if not self_test(config):
        safe_log("error", "Self-test failed. Please fix the issues.")
        sys.exit(1)

    face_system = FaceIDSystem(config)

    if config["web_api"]["enabled"]:
        try:
            api = FaceIDAPI(face_system, config)
            api_thread = threading.Thread(target=api.run, daemon=True)
            api_thread.start()
            safe_log("info", "Web API started in background")
        except Exception as e:
            safe_log("error", f"Failed to start web API: {e}")

    run_menu(face_system, config)
    safe_log("info", "Program finished")

