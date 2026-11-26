import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from faceid.utils import safe_log

try:
    from scipy.optimize import linear_sum_assignment

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


@dataclass
class FaceBox:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float = 1.0
    landmarks: Optional[np.ndarray] = None

    def width(self) -> int:
        return self.x2 - self.x1

    def height(self) -> int:
        return self.y2 - self.y1

    def area(self) -> int:
        return self.width() * self.height()

    def center(self) -> Tuple[float, float]:
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2

    @classmethod
    def from_array(
        cls,
        arr: np.ndarray,
        confidence: float = 1.0,
        landmarks: Optional[np.ndarray] = None,
    ):
        x1, y1, x2, y2 = map(int, arr)
        return cls(x1, y1, x2, y2, confidence, landmarks)


@dataclass
class TrackedFace:
    track_id: int
    bbox: FaceBox
    embedding: Optional[np.ndarray] = None
    name: Optional[str] = None
    similarity: float = 0.0
    hits: int = 1
    disappeared: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


class FaceTracker:
    def __init__(self, config: Dict):
        self.max_disappeared = config["tracking"]["max_disappeared"]
        self.iou_threshold = config["tracking"]["iou_threshold"]
        self.use_hungarian = config["tracking"]["use_hungarian"] and SCIPY_AVAILABLE
        self.min_face_size = config["tracking"]["min_face_size"]
        self.tracks: Dict[int, TrackedFace] = {}
        self.next_id = 0

    @staticmethod
    def compute_iou(box1: FaceBox, box2: FaceBox) -> float:
        x1 = max(box1.x1, box2.x1)
        y1 = max(box1.y1, box2.y1)
        x2 = min(box1.x2, box2.x2)
        y2 = min(box1.y2, box2.y2)
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        union_area = box1.area() + box2.area() - inter_area
        return inter_area / union_area if union_area > 0 else 0.0

    def update(self, detections: List[FaceBox], frame_shape: Tuple[int, int]) -> List[TrackedFace]:
        current_time = time.time()
        filtered_dets = [
            d
            for d in detections
            if d.width() >= self.min_face_size and d.height() >= self.min_face_size
        ]

        if not filtered_dets:
            for track in self.tracks.values():
                track.disappeared += 1
            self._remove_lost_tracks()
            return list(self.tracks.values())

        if not self.tracks:
            for det in filtered_dets:
                self.tracks[self.next_id] = TrackedFace(track_id=self.next_id, bbox=det)
                self.next_id += 1
            return list(self.tracks.values())

        track_ids = list(self.tracks.keys())
        track_boxes = [self.tracks[tid].bbox for tid in track_ids]

        if self.use_hungarian:
            cost_matrix = np.zeros((len(track_ids), len(filtered_dets)))
            for i, t_box in enumerate(track_boxes):
                for j, d_box in enumerate(filtered_dets):
                    cost_matrix[i, j] = 1.0 - self.compute_iou(t_box, d_box)
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            matches = []
            for r, c in zip(row_ind, col_ind):
                if cost_matrix[r, c] < 1.0 - self.iou_threshold:
                    matches.append((track_ids[r], c))
        else:
            matches = []
            used_dets = set()
            for tid in track_ids:
                t_box = self.tracks[tid].bbox
                best_iou = self.iou_threshold
                best_idx = -1
                for i, d_box in enumerate(filtered_dets):
                    if i in used_dets:
                        continue
                    iou = self.compute_iou(t_box, d_box)
                    if iou > best_iou:
                        best_iou = iou
                        best_idx = i
                if best_idx >= 0:
                    matches.append((tid, best_idx))
                    used_dets.add(best_idx)

        matched_track_ids = set()
        for tid, det_idx in matches:
            track = self.tracks[tid]
            track.bbox = filtered_dets[det_idx]
            track.hits += 1
            track.disappeared = 0
            track.last_seen = current_time
            matched_track_ids.add(tid)

        for tid in track_ids:
            if tid not in matched_track_ids:
                self.tracks[tid].disappeared += 1

        matched_det_indices = {idx for _, idx in matches}
        for i, det in enumerate(filtered_dets):
            if i not in matched_det_indices:
                self.tracks[self.next_id] = TrackedFace(track_id=self.next_id, bbox=det)
                self.next_id += 1

        self._remove_lost_tracks()
        return list(self.tracks.values())

    def _remove_lost_tracks(self):
        to_delete = [
            tid
            for tid, track in self.tracks.items()
            if track.disappeared > self.max_disappeared
        ]
        for tid in to_delete:
            del self.tracks[tid]
            safe_log("debug", f"Track {tid} removed")

