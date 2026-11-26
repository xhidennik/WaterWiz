from typing import Optional, Tuple

import cv2
import numpy as np


class FaceAligner:
    """
    Выравнивает лицо по 5 ключевым точкам (глаза, нос, уголки рта).
    Используется аффинное преобразование к стандартным координатам FaceNet.
    """

    def __init__(self, desired_face_width: int = 160, desired_face_height: int = 160):
        self.desired_size: Tuple[int, int] = (desired_face_width, desired_face_height)
        # Пропорции расположения опорных точек в целевом размере (160x160 по умолчанию)
        self.desired_left_eye = (0.35, 0.35)
        self.desired_right_eye = (0.65, 0.35)
        self.desired_nose = (0.5, 0.55)

    def align(self, image: np.ndarray, landmarks: np.ndarray) -> Optional[np.ndarray]:
        """
        Принимает BGR-изображение и landmarks (5,2) от MTCNN.
        Возвращает выровненное лицо размера desired_size или None при ошибке.
        """
        if landmarks is None or landmarks.shape != (5, 2):
            return None

        left_eye = landmarks[0]
        right_eye = landmarks[1]
        nose = landmarks[2]

        dw, dh = self.desired_size
        desired_left_eye_px = (self.desired_left_eye[0] * dw, self.desired_left_eye[1] * dh)
        desired_right_eye_px = (
            self.desired_right_eye[0] * dw,
            self.desired_right_eye[1] * dh,
        )
        desired_nose_px = (self.desired_nose[0] * dw, self.desired_nose[1] * dh)

        src_pts = np.float32([left_eye, right_eye, nose])
        dst_pts = np.float32([desired_left_eye_px, desired_right_eye_px, desired_nose_px])

        M = cv2.getAffineTransform(src_pts, dst_pts)
        return cv2.warpAffine(image, M, self.desired_size, flags=cv2.INTER_CUBIC)

