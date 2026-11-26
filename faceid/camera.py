import time
import queue
import threading
from collections import deque
from typing import Any, Dict, Optional, Tuple

import cv2

from faceid.utils import safe_log


class CameraManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cap: Optional[cv2.VideoCapture] = None
        self.frame_queue = queue.Queue(maxsize=config["performance"]["frame_queue_size"])
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.actual_fps = 0.0
        self.actual_resolution = (0, 0)
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.fps_history = deque(maxlen=30)

    def open(self) -> bool:
        device_id = self.config["camera"]["device_id"]
        target_w = self.config["camera"]["target_width"]
        target_h = self.config["camera"]["target_height"]
        target_fps = self.config["camera"]["target_fps"]
        backend_str = self.config["camera"]["backend"]

        if backend_str == "ds_any":
            backends = [cv2.CAP_DSHOW, cv2.CAP_ANY]
        elif backend_str == "dshow":
            backends = [cv2.CAP_DSHOW]
        else:
            backends = [cv2.CAP_ANY]

        for backend in backends:
            cap = cv2.VideoCapture(device_id, backend)
            if not cap.isOpened():
                continue

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_w)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_h)
            cap.set(cv2.CAP_PROP_FPS, target_fps)

            actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)

            ret, _ = cap.read()
            if ret:
                self.cap = cap
                self.actual_resolution = (actual_w, actual_h)
                self.actual_fps = actual_fps if actual_fps > 0 else target_fps
                safe_log(
                    "info",
                    f"Camera opened: {actual_w}x{actual_h}, {self.actual_fps:.1f} FPS (backend={backend})",
                )
                return True
            cap.release()

        safe_log("error", "Failed to open camera")
        return False

    def start_capture_thread(self):
        if self.cap is None:
            raise RuntimeError("Camera not opened")
        self.running = True
        self.thread = threading.Thread(
            target=self._capture_loop, name="CameraThread", daemon=True
        )
        self.thread.start()
        safe_log("debug", "Capture thread started")

    def _capture_loop(self):
        fps_limit = self.config["performance"]["fps_limit"]
        frame_interval = 1.0 / fps_limit if fps_limit > 0 else 0
        next_frame_time = time.time()

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                safe_log("warning", "Failed to grab frame")
                time.sleep(0.01)
                continue

            current_time = time.time()
            if current_time >= next_frame_time:
                try:
                    self.frame_queue.put_nowait((current_time, frame))
                except queue.Full:
                    pass

                next_frame_time = max(current_time, next_frame_time) + frame_interval

                self.frame_count += 1
                now = time.time()
                if now - self.last_frame_time >= 1.0:
                    self.actual_fps = self.frame_count / (now - self.last_frame_time)
                    self.fps_history.append(self.actual_fps)
                    self.frame_count = 0
                    self.last_frame_time = now
            else:
                time.sleep(0.001)

    def get_frame(self, timeout: float = 0.1) -> Optional[Tuple[float, Any]]:
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        safe_log("debug", "Camera stopped")

    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

