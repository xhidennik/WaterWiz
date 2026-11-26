import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
from facenet_pytorch import MTCNN, InceptionResnetV1
from torchvision import transforms

from faceid.alignment import FaceAligner
from faceid.camera import CameraManager
from faceid.database import FaceDatabase
from faceid.tracking import FaceBox, FaceTracker
from faceid.utils import get_device, safe_log


@dataclass
class RecognitionResult:
    success: bool
    name: Optional[str]
    similarity: float
    message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "success": bool(self.success),
            "name": self.name,
            "similarity": float(self.similarity),
            "message": self.message,
            "timestamp": self.timestamp,
        }


class FaceIDSystem:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = FaceDatabase(config)
        self.device = get_device(config)
        safe_log("info", f"Using device: {self.device}")

        self.mtcnn = MTCNN(
            keep_all=True,
            device=self.device,
            min_face_size=config["tracking"]["min_face_size"],
            thresholds=[0.6, 0.7, 0.8],
            factor=0.709,
            post_process=False,
        )
        self.resnet = (
            InceptionResnetV1(
                pretrained=config["recognition"]["model_name"],
                classify=False,
                device=self.device,
            )
            .eval()
            .to(self.device)
        )

        self.aligner = (
            FaceAligner(
                desired_face_width=config["recognition"]["face_size"],
                desired_face_height=config["recognition"]["face_size"],
            )
            if config["recognition"].get("use_alignment", True)
            else None
        )

        self.tracker = FaceTracker(config)
        self.camera: Optional[CameraManager] = None

        self.stats = {
            "frames_processed": 0,
            "faces_detected": 0,
            "recognitions": 0,
            "start_time": time.time(),
        }
        self._lock = threading.RLock()

        self.clahe = (
            cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            if config["recognition"].get("apply_clahe", False)
            else None
        )

        self._embedding_transform = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            ]
        )

    def _preprocess_face(
        self, face_img: np.ndarray, landmarks: Optional[np.ndarray] = None
    ) -> Optional[np.ndarray]:
        """Выравнивание и улучшение контраста. landmarks должны быть в координатах face_img."""
        if face_img.size == 0:
            return None

        face_size = self.config["recognition"]["face_size"]

        if self.aligner is not None and landmarks is not None:
            aligned = self.aligner.align(face_img, landmarks)
            if aligned is None:
                aligned = cv2.resize(face_img, (face_size, face_size))
        else:
            aligned = cv2.resize(face_img, (face_size, face_size))

        if self.clahe is not None:
            lab = cv2.cvtColor(aligned, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = self.clahe.apply(l)
            lab = cv2.merge((l, a, b))
            aligned = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return aligned

    def _extract_embedding(self, full_frame: np.ndarray, face_box: FaceBox) -> Optional[np.ndarray]:
        """
        full_frame – полный кадр, face_box – bbox + landmarks (в координатах полного кадра).
        Возвращает L2‑нормализованный эмбеддинг.
        """
        x1, y1, x2, y2 = face_box.x1, face_box.y1, face_box.x2, face_box.y2
        h, w = full_frame.shape[:2]
        # Безопасные границы
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        if x2 <= x1 or y2 <= y1:
            return None

        face_crop = full_frame[y1:y2, x1:x2]

        # Пересчитываем landmarks в координаты кропа
        landmarks = None
        if face_box.landmarks is not None:
            landmarks = face_box.landmarks.copy()
            landmarks[:, 0] -= x1
            landmarks[:, 1] -= y1

        processed = self._preprocess_face(face_crop, landmarks)
        if processed is None:
            return None

        try:
            face_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            face_tensor = self._embedding_transform(face_rgb).unsqueeze(0).to(self.device)

            with torch.no_grad():
                embedding = self.resnet(face_tensor).cpu().numpy().flatten()

            # L2 нормализация
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            return embedding.astype(np.float32)
        except Exception as e:
            safe_log("error", f"Embedding extraction error: {e}")
            return None

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b))

    def _identify(self, query_emb: np.ndarray) -> Tuple[Optional[str], float]:
        if self.db.is_empty():
            return None, 0.0

        all_embs, names = self.db.get_all_embeddings()
        if not all_embs:
            return None, 0.0

        similarities = [self._cosine_similarity(emb, query_emb) for emb in all_embs]
        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])
        best_name = names[best_idx]

        threshold = self.config["recognition"]["similarity_threshold"]
        if best_sim > threshold:
            return best_name, best_sim
        return None, best_sim

    def detect_faces(self, frame: np.ndarray) -> List[FaceBox]:
        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            boxes, probs, landmarks = self.mtcnn.detect(frame_rgb, landmarks=True)
            if boxes is None:
                return []

            faces: List[FaceBox] = []
            for i, box in enumerate(boxes):
                if probs is not None and probs[i] < 0.95:
                    continue
                landmarks_arr = landmarks[i] if landmarks is not None else None
                conf = float(probs[i]) if probs is not None else 1.0
                faces.append(FaceBox.from_array(box, conf, landmarks_arr))

            with self._lock:
                self.stats["faces_detected"] += len(faces)
            return faces
        except Exception as e:
            safe_log("error", f"Detection error: {e}")
            return []

    def register_user(
        self,
        name: str,
        image_path: Optional[str] = None,
        capture_from_cam: bool = True,
        num_samples: int = 3,
    ) -> bool:
        if image_path:
            img = cv2.imread(image_path)
            if img is None:
                safe_log("error", f"Could not load {image_path}")
                return False
            faces = self.detect_faces(img)
            if not faces:
                safe_log("error", "No face found in image")
                return False
            face = max(faces, key=lambda f: f.area())
            emb = self._extract_embedding(img, face)          # ← исправлено
            if emb is None:
                return False
            self.db.add_user(
                name,
                emb,
                {"registration_method": "file"},
                face_image=img[face.y1 : face.y2, face.x1 : face.x2],
            )
            return True

        if capture_from_cam:
            cam = CameraManager(self.config)
            if not cam.open():
                safe_log("error", "Could not open camera for registration")
                return False

            safe_log("info", f"Registering '{name}'. Press 's' to capture, 'q' to cancel.")
            embeddings: List[np.ndarray] = []
            face_images: List[np.ndarray] = []

            cv2.namedWindow("Registration")
            sample_count = 0
            while sample_count < num_samples:
                ret, frame = cam.cap.read()
                if not ret:
                    continue

                display = frame.copy()
                faces = self.detect_faces(frame)
                for face in faces:
                    cv2.rectangle(
                        display, (face.x1, face.y1), (face.x2, face.y2), (0, 255, 0), 2
                    )
                    if face.landmarks is not None:
                        for (x, y) in face.landmarks.astype(int):
                            cv2.circle(display, (x, y), 2, (0, 0, 255), -1)

                cv2.putText(
                    display,
                    f"Samples: {sample_count}/{num_samples}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("Registration", display)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("s") and faces:
                    face = max(faces, key=lambda f: f.area())
                    emb = self._extract_embedding(frame, face)   # ← исправлено
                    if emb is not None:
                        embeddings.append(emb)
                        h, w = frame.shape[:2]
                        x1 = max(0, min(face.x1, w - 1))
                        y1 = max(0, min(face.y1, h - 1))
                        x2 = max(0, min(face.x2, w))
                        y2 = max(0, min(face.y2, h))
                        crop = frame[y1:y2, x1:x2]
                        face_images.append(crop if crop.size else None)
                        sample_count += 1
                        safe_log("info", f"Sample {sample_count} captured")
                elif key == ord("q"):
                    break

            cv2.destroyWindow("Registration")
            cam.stop()

            if not embeddings:
                return False

            for i, emb in enumerate(embeddings):
                self.db.add_user(
                    name,
                    emb,
                    {
                        "registration_method": "camera",
                        "samples_collected": len(embeddings),
                    },
                    face_image=face_images[i] if i < len(face_images) else None,
                )
            return True

        return False

    def verify_user(
        self,
        claimed_name: str,
        full_frame: np.ndarray,
        face_box: FaceBox,
    ) -> RecognitionResult:
        stored_embs = self.db.get_user_embeddings(claimed_name)
        if stored_embs is None or len(stored_embs) == 0:
            return RecognitionResult(False, None, 0.0, f"User '{claimed_name}' not found")

        query_emb = self._extract_embedding(full_frame, face_box)
        if query_emb is None:
            return RecognitionResult(False, None, 0.0, "Failed to extract embedding")

        max_sim = max(self._cosine_similarity(emb, query_emb) for emb in stored_embs)
        threshold = self.config["recognition"]["similarity_threshold"]
        success = max_sim > threshold
        with self._lock:
            self.stats["recognitions"] += 1
        return RecognitionResult(
            success,
            claimed_name if success else None,
            float(max_sim),
            f"Similarity: {max_sim:.3f} (threshold: {threshold})",
        )

    def identify_face(
        self, full_frame: np.ndarray, face_box: FaceBox
    ) -> RecognitionResult:
        query_emb = self._extract_embedding(full_frame, face_box)
        if query_emb is None:
            return RecognitionResult(False, None, 0.0, "Failed to extract embedding")
        name, sim = self._identify(query_emb)
        with self._lock:
            self.stats["recognitions"] += 1
        threshold = self.config["recognition"]["similarity_threshold"]
        return RecognitionResult(
            name is not None,
            name,
            float(sim),
            f"Similarity: {sim:.3f} (threshold: {threshold})",
        )

    def process_frame(self, frame: np.ndarray, timestamp: float) -> np.ndarray:
        with self._lock:
            self.stats["frames_processed"] += 1
        faces = self.detect_faces(frame)
        tracked = self.tracker.update(faces, frame.shape[:2])
        interval = self.config["recognition"]["detection_interval"]

        for track in tracked:
            if track.embedding is None or (
                track.hits % interval == 0 and track.disappeared == 0
            ):
                # track.bbox – это FaceBox с landmarks в координатах полного кадра
                emb = self._extract_embedding(frame, track.bbox)
                if emb is not None:
                    track.embedding = emb
                    name, sim = self._identify(emb)
                    track.name = name
                    track.similarity = sim

        annotated = frame.copy()
        for track in tracked:
            color = (0, 255, 0) if track.name else (0, 165, 255)
            cv2.rectangle(
                annotated,
                (track.bbox.x1, track.bbox.y1),
                (track.bbox.x2, track.bbox.y2),
                color,
                2,
            )
            label = track.name if track.name else f"ID:{track.track_id}"
            if track.similarity > 0:
                label += f" ({track.similarity:.2f})"
            cv2.putText(
                annotated,
                label,
                (track.bbox.x1, track.bbox.y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

            if (
                self.config["debug"].get("draw_landmarks", False)
                and track.bbox.landmarks is not None
            ):
                for (x, y) in track.bbox.landmarks.astype(int):
                    cv2.circle(annotated, (x, y), 1, (255, 255, 255), -1)

        if self.camera:
            fps_text = f"FPS: {self.camera.actual_fps:.1f}"
            cv2.putText(
                annotated,
                fps_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 255),
                2,
            )
        return annotated

    def run_live_recognition(self):
        self.camera = CameraManager(self.config)
        if not self.camera.open():
            safe_log("error", "Could not open camera")
            return

        self.camera.start_capture_thread()
        safe_log("info", "Live recognition started. Press 'q' to quit, 'r' to register.")
        cv2.namedWindow("Face ID - Live")

        while True:
            frame_data = self.camera.get_frame()
            if frame_data is None:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("r"):
                    name = input("Enter name to register: ").strip()
                    if name:
                        self.camera.stop()
                        self.register_user(name, capture_from_cam=True, num_samples=3)
                        self.camera.open()
                        self.camera.start_capture_thread()
                continue

            timestamp, frame = frame_data
            annotated = self.process_frame(frame, timestamp)
            cv2.imshow("Face ID - Live", annotated)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                name = input("Enter name to register: ").strip()
                if name:
                    self.camera.stop()
                    self.register_user(name, capture_from_cam=True, num_samples=3)
                    self.camera.open()
                    self.camera.start_capture_thread()

        self.camera.stop()
        cv2.destroyAllWindows()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            s = self.stats.copy()
            s["uptime"] = time.time() - s["start_time"]
            s["users_count"] = len(self.db.user_embeddings)
            if self.camera:
                s["camera_fps"] = self.camera.actual_fps
            return s