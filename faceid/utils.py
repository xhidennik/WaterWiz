import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any, Dict

import cv2
import torch


def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    log_level = getattr(logging, config["logging"]["level"].upper(), logging.INFO)
    log_file = Path(config["logging"]["file"])
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("FaceID")
    logger.setLevel(log_level)

    # Avoid duplicate handlers when re-importing in interactive sessions.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=config["logging"]["max_bytes"],
        backupCount=config["logging"]["backup_count"],
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console_handler)

    return logger


def safe_log(level: str, message: str):
    """
    Logging helper used across modules.
    Uses the shared 'FaceID' logger (created by setup_logging), or prints if missing.
    """
    logger = logging.getLogger("FaceID")
    if logger.handlers:
        log_func = getattr(logger, level, logger.info)
        log_func(message)
    else:
        print(f"[{level.upper()}] {message}")


def get_device(config: Dict[str, Any]) -> torch.device:
    dev_cfg = config["recognition"]["device"]
    if dev_cfg == "cuda" and torch.cuda.is_available():
        return torch.device("cuda:0")
    if dev_cfg == "cpu":
        return torch.device("cpu")
    return torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


def self_test(config: Dict[str, Any]) -> bool:
    print("\n" + "=" * 60)
    print("RUNNING SYSTEM SELF-TEST")
    print("=" * 60)
    errors = []
    warnings = []

    print("\n[1] Checking environment...")
    print(f"   Python: {sys.version}")
    print(f"   OpenCV: {cv2.__version__}")
    print(f"   PyTorch: {torch.__version__}")
    if torch.cuda.is_available():
        print(f"   CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        warnings.append("CUDA not available, using CPU (install PyTorch with CUDA 11.8)")

    print("\n[2] Checking camera...")
    from faceid.camera import CameraManager

    cam = CameraManager(config)
    if cam.open():
        print(f"   Camera works: {cam.actual_resolution[0]}x{cam.actual_resolution[1]}")
        cam.stop()
    else:
        errors.append("Failed to open camera")

    print("\n[3] Loading models...")
    try:
        from facenet_pytorch import MTCNN, InceptionResnetV1

        device = get_device(config)
        _ = MTCNN(keep_all=True, device=device)
        _ = InceptionResnetV1(pretrained="vggface2").eval().to(device)
        print("   Models loaded successfully")
    except Exception as e:
        errors.append(f"Model loading error: {e}")

    print("\n[4] Checking filesystem...")
    db_path = Path(config["database"]["path"])
    try:
        db_path.mkdir(exist_ok=True)
        test_file = db_path / ".test"
        test_file.touch()
        test_file.unlink()
        print("   Write permission OK")
    except Exception as e:
        errors.append(f"No write permission in {db_path}: {e}")

    print("\n" + "=" * 60)
    if errors:
        print("CRITICAL ERRORS:")
        for err in errors:
            print(f"   - {err}")
        return False

    print("ALL CHECKS PASSED")
    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"   - {warn}")
    return True

