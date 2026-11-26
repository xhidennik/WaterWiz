import json
import shutil
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from faceid.utils import safe_log


class FaceDatabase:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_path = Path(config["database"]["path"])
        self.db_path.mkdir(exist_ok=True)
        self.images_dir = self.db_path / "images"
        if config["database"].get("save_face_images", True):
            self.images_dir.mkdir(exist_ok=True)

        # Для каждого пользователя список эмбеддингов
        self.user_embeddings: Dict[str, List[np.ndarray]] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

        self.max_samples = config["recognition"].get("max_samples_per_user", 5)

        self._load()

    @staticmethod
    def _normalize_embedding(emb: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(emb)
        return emb / norm if norm > 0 else emb

    def _load(self):
        with self._lock:
            old_emb_file = self.db_path / "embeddings.npy"
            old_users_file = self.db_path / "users.json"
            if old_emb_file.exists() and old_users_file.exists():
                old_emb = np.load(old_emb_file)
                with open(old_users_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    old_names = data.get("names", [])

                backup_dir = self.db_path / "old_format_backup"
                backup_dir.mkdir(exist_ok=True)
                shutil.move(str(old_emb_file), str(backup_dir / "embeddings.npy"))
                shutil.move(str(old_users_file), str(backup_dir / "users.json"))
                if (self.db_path / "meta.json").exists():
                    shutil.move(str(self.db_path / "meta.json"), str(backup_dir / "meta.json"))

                for name, emb in zip(old_names, old_emb):
                    emb_norm = self._normalize_embedding(emb)
                    self.user_embeddings[name] = [emb_norm]
                    self.metadata.setdefault(name, {"created": time.time()})

                safe_log("info", f"Converted old database: {len(old_names)} users")
                self._save()
                return

            users_meta_file = self.db_path / "users_meta.json"
            embeddings_dir = self.db_path / "embeddings"
            if users_meta_file.exists() and embeddings_dir.exists():
                with open(users_meta_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
                for name in self.metadata.keys():
                    user_emb_path = embeddings_dir / f"{name}.npy"
                    if user_emb_path.exists():
                        embs = np.load(user_emb_path)
                        self.user_embeddings[name] = [
                            self._normalize_embedding(e) for e in embs
                        ]
                safe_log("info", f"Loaded {len(self.user_embeddings)} users from database")
            else:
                self._save()

    def _save(self):
        with self._lock:
            with open(self.db_path / "users_meta.json", "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)

            embeddings_dir = self.db_path / "embeddings"
            embeddings_dir.mkdir(exist_ok=True)
            for name, emb_list in self.user_embeddings.items():
                np.save(embeddings_dir / f"{name}.npy", np.array(emb_list))

            for f in embeddings_dir.glob("*.npy"):
                if f.stem not in self.user_embeddings:
                    f.unlink()

    def _save_face_image(self, name: str, face_image: np.ndarray) -> Optional[str]:
        if face_image is None or not self.config["database"].get("save_face_images", True):
            return None

        # Guard against empty crops (OpenCV will throw on imwrite with empty image)
        try:
            if getattr(face_image, "size", 0) == 0:
                return None
        except Exception:
            return None

        # Use ns timestamp to avoid collisions when capturing multiple samples quickly.
        img_filename = self.images_dir / f"{name}_{time.time_ns()}.jpg"
        ok = cv2.imwrite(str(img_filename), face_image)
        if not ok:
            return None
        return str(img_filename)

    def add_user(
        self,
        name: str,
        embedding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
        face_image: Optional[np.ndarray] = None,
    ):
        emb_norm = self._normalize_embedding(embedding)
        with self._lock:
            if name not in self.user_embeddings:
                self.user_embeddings[name] = []
                self.metadata[name] = metadata or {"created": time.time()}
            else:
                if metadata:
                    self.metadata[name].update(metadata)

            self.user_embeddings[name].append(emb_norm)
            if len(self.user_embeddings[name]) > self.max_samples:
                self.user_embeddings[name].pop(0)

            saved_path = self._save_face_image(name, face_image)
            if saved_path:
                self.metadata.setdefault(name, {})
                self.metadata[name].setdefault("images", [])
                self.metadata[name]["images"].append(saved_path)

            self._save()
            safe_log(
                "info",
                f"User '{name}' added/updated (samples: {len(self.user_embeddings[name])})",
            )

    def remove_user(self, name: str) -> bool:
        with self._lock:
            if name not in self.user_embeddings:
                return False
            del self.user_embeddings[name]
            self.metadata.pop(name, None)
            self._save()
            safe_log("info", f"User '{name}' removed")
            return True

    def get_all_embeddings(self) -> Tuple[List[np.ndarray], List[str]]:
        with self._lock:
            all_embs: List[np.ndarray] = []
            names: List[str] = []
            for name, emb_list in self.user_embeddings.items():
                all_embs.extend(emb_list)
                names.extend([name] * len(emb_list))
            return all_embs, names

    def get_user_embeddings(self, name: str) -> Optional[List[np.ndarray]]:
        with self._lock:
            if name in self.user_embeddings:
                return [emb.copy() for emb in self.user_embeddings[name]]
            return None

    def is_empty(self) -> bool:
        with self._lock:
            return len(self.user_embeddings) == 0

    def list_users(self) -> List[Dict[str, Any]]:
        with self._lock:
            users = []
            for name, meta in self.metadata.items():
                users.append(
                    {
                        "name": name,
                        "metadata": meta,
                        "samples": len(self.user_embeddings.get(name, [])),
                    }
                )
            return users

