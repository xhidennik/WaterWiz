import base64
import logging
import time
from typing import Any, Dict

import cv2
import numpy as np
from flask import Flask, jsonify, request

from faceid.system import FaceIDSystem

logger = logging.getLogger("FaceID")


class FaceIDAPI:
    def __init__(self, face_system: FaceIDSystem, config: Dict[str, Any]):
        self.face_system = face_system
        self.config = config
        self.app = Flask(__name__)
        self.auth_token = config["web_api"]["auth_token"]
        self._setup_routes()

    def _check_auth(self, req) -> bool:
        if self.auth_token:
            token = req.headers.get("Authorization", "").replace("Bearer ", "")
            return token == self.auth_token
        return True

    @staticmethod
    def _decode_image_from_b64(image_b64: str) -> np.ndarray:
        img_data = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image")
        return img

    def _setup_routes(self):
        @self.app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "ok", "model_loaded": True,
                            "uptime": time.time() - self.face_system.stats["start_time"]})

        @self.app.route("/extract", methods=["POST"])
        def extract():
            if not self._check_auth(request):
                logger.warning("/extract auth failed")
                return jsonify({"error": "Unauthorized"}), 401

            data = request.get_json()
            if not data or "image" not in data:
                logger.warning("/extract missing image field")
                return jsonify({"error": "Missing image"}), 400

            image_b64 = data["image"]
            logger.info("/extract received image (%d chars)", len(image_b64))

            try:
                img = self._decode_image_from_b64(image_b64)
                logger.info("Image decoded successfully (%s)", img.shape)
            except Exception as e:
                logger.error("/extract image decode failed: %s", e)
                return jsonify({"error": f"Image decode error: {e}"}), 400

            start = time.time()
            faces = self.face_system.detect_faces(img)
            elapsed = time.time() - start
            logger.info("Detection took %.2fs, found %d faces", elapsed, len(faces))

            if not faces:
                logger.warning("/extract no face detected")
                return jsonify({"success": False, "face_detected": False, "message": "No face detected"})

            face = max(faces, key=lambda f: f.area())
            logger.info("Using largest face: (%d,%d)-(%d,%d) area=%d",
                        face.x1, face.y1, face.x2, face.y2, face.area())

            start = time.time()
            embedding = self.face_system._extract_embedding(img, face)
            elapsed = time.time() - start
            logger.info("Embedding extraction took %.2fs", elapsed)

            if embedding is None:
                logger.error("/extract embedding extraction returned None")
                return jsonify({"success": False, "face_detected": True, "message": "Failed to extract embedding"})

            logger.info("/extract success: embedding dim=%d, norm=%.4f",
                        len(embedding), float(np.linalg.norm(embedding)))
            return jsonify({
                "success": True,
                "face_detected": True,
                "embedding": embedding.tolist(),
                "bbox": {
                    "x1": face.x1, "y1": face.y1,
                    "x2": face.x2, "y2": face.y2,
                },
                "message": "OK",
            })

    def run(self):
        host = self.config["web_api"]["host"]
        port = self.config["web_api"]["port"]
        from faceid.utils import safe_log

        safe_log("info", f"FaceID API running on http://{host}:{port}")
        self.app.run(host=host, port=port, threaded=True)
