import json
import time
from datetime import datetime
from typing import Any, Dict

import cv2

from faceid.camera import CameraManager
from faceid.system import FaceIDSystem
from faceid.utils import safe_log


def verify_via_camera(
    face_system: FaceIDSystem, config: Dict[str, Any], claimed_name: str, timeout: float = 10.0
) -> Dict[str, Any]:
    cam = CameraManager(config)
    if not cam.open():
        return {"success": False, "message": "Camera unavailable"}

    safe_log("info", f"Verification started for '{claimed_name}'. Press 'q' to cancel.")
    cv2.namedWindow("Verification - Press Q to cancel")

    result: Dict[str, Any] = {"success": False, "message": "Not verified"}
    start_time = time.time()

    while time.time() - start_time < timeout:
        ret, frame = cam.cap.read()
        if not ret:
            continue

        display = frame.copy()
        faces = face_system.detect_faces(frame)
        for face in faces:
            cv2.rectangle(display, (face.x1, face.y1), (face.x2, face.y2), (0, 255, 0), 2)

        cv2.putText(
            display,
            f"Verifying: {claimed_name}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        cv2.putText(
            display,
            "Press Q to cancel",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )
        cv2.imshow("Verification - Press Q to cancel", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            result = {"success": False, "message": "Cancelled by user"}
            break

        if faces:
            face = max(faces, key=lambda f: f.area())
            res = face_system.verify_user(claimed_name, frame, face)
            result = res.to_dict()
            if res.success:
                cv2.putText(
                    display,
                    "ACCESS GRANTED",
                    (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("Verification - Press Q to cancel", display)
                cv2.waitKey(1000)
                break
            cv2.putText(
                display,
                "ACCESS DENIED",
                (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )
            cv2.imshow("Verification - Press Q to cancel", display)

    cam.stop()
    cv2.destroyAllWindows()
    return result


def run_menu(face_system: FaceIDSystem, config: Dict[str, Any]):
    print("\n=== MAIN MENU ===")
    print("r - Register new user")
    print("l - Live recognition")
    print("w - Verification (camera)")
    print("d - Delete user")
    print("u - List users")
    print("s - Statistics")
    print("q - Quit")

    while True:
        try:
            choice = input("\nChoose action: ").strip().lower()
        except EOFError:
            break

        if choice == "r":
            name = input("User name: ").strip()
            if not name:
                continue
            path = input("Photo path (Enter for camera): ").strip()
            if path:
                face_system.register_user(name, image_path=path, capture_from_cam=False)
            else:
                face_system.register_user(name, capture_from_cam=True, num_samples=3)

        elif choice == "l":
            face_system.run_live_recognition()

        elif choice == "w":
            claimed = input("User name to verify: ").strip()
            if claimed:
                res = verify_via_camera(face_system, config, claimed)
                print("\nVerification result:")
                print(json.dumps(res, indent=2, ensure_ascii=False))

        elif choice == "d":
            name = input("User name to delete: ").strip()
            if face_system.db.remove_user(name):
                print(f"User '{name}' deleted")
            else:
                print("User not found")

        elif choice == "u":
            users = face_system.db.list_users()
            if users:
                for u in users:
                    created = u["metadata"].get("created", 0)
                    samples = u.get("samples", 0)
                    try:
                        created_dt = datetime.fromtimestamp(created)
                    except Exception:
                        created_dt = created
                    print(f" - {u['name']} (created: {created_dt}, samples: {samples})")
            else:
                print("Database empty")

        elif choice == "s":
            stats = face_system.get_stats()
            print(json.dumps(stats, indent=2, ensure_ascii=False))

        elif choice == "q":
            break
        else:
            print("Unknown command")

