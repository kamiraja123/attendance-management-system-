"""
Face Recognition and Detection Module.
Provides dual-engine architecture:
1. `face_recognition` (dlib 128D deep encodings) if available.
2. OpenCV LBPH Face Recognizer (built-in, offline, high-speed fallback).

Handles:
- Face detection via OpenCV Haar Cascades
- Face sample capture and dataset management
- Model training and encodings persistence
- Real-time prediction and stylish HUD bounding box rendering
"""

import os
import shutil
import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import cv2
import numpy as np

from utils import DATASET_DIR, ENCODINGS_DIR, BASE_DIR

# Check if dlib-based `face_recognition` is installed
try:
    import face_recognition
    HAS_FACE_RECOGNITION_LIB = True
except ImportError:
    face_recognition = None
    HAS_FACE_RECOGNITION_LIB = False

# Paths for saved models & mappings
LBPH_MODEL_PATH = ENCODINGS_DIR / "lbph_classifier.yml"
LABELS_MAP_PATH = ENCODINGS_DIR / "labels_map.json"
DLIB_ENCODINGS_PATH = ENCODINGS_DIR / "encodings.pkl"

# Initialize Haar Cascade Classifier for face detection
LOCAL_HAAR_PATH = BASE_DIR / "haarcascade_frontalface_default.xml"
if LOCAL_HAAR_PATH.exists():
    HAAR_CASCADE_PATH = str(LOCAL_HAAR_PATH)
else:
    HAAR_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(HAAR_CASCADE_PATH)


class FaceRecognizerManager:
    """
    Manages face detection, dataset storage, model training, and recognition.
    Supports both `face_recognition` (dlib) and OpenCV LBPH.
    """

    def __init__(self, prefer_face_recognition_lib: bool = True):
        self.use_dlib = HAS_FACE_RECOGNITION_LIB and prefer_face_recognition_lib
        self.lbph_recognizer: Optional[cv2.face.LBPHFaceRecognizer] = None
        self.labels_to_id: Dict[int, str] = {}  # int -> person_id
        self.id_to_labels: Dict[str, int] = {}  # person_id -> int
        self.dlib_known_encodings: List[np.ndarray] = []
        self.dlib_known_ids: List[str] = []

        # Confidence threshold for LBPH (lower score = higher similarity)
        # Typically < 65-75 is a genuine match, > 80 is unknown
        self.lbph_threshold = 68.0

        # Load existing models on startup
        self.load_model()

    def get_engine_name(self) -> str:
        """Returns the active face recognition engine name."""
        if self.use_dlib:
            return "face_recognition (dlib 128D)"
        return "OpenCV LBPH Face Recognizer"

    def is_model_trained(self) -> bool:
        """Checks if a trained model or encoding file exists."""
        if self.use_dlib:
            return DLIB_ENCODINGS_PATH.exists() and len(self.dlib_known_ids) > 0
        return LBPH_MODEL_PATH.exists() and len(self.labels_to_id) > 0

    def load_model(self) -> bool:
        """Loads trained weights and label mappings from disk."""
        try:
            if self.use_dlib:
                if DLIB_ENCODINGS_PATH.exists():
                    with open(DLIB_ENCODINGS_PATH, "rb") as f:
                        data = pickle.load(f)
                        self.dlib_known_encodings = data.get("encodings", [])
                        self.dlib_known_ids = data.get("ids", [])
                    return True
                return False
            else:
                if hasattr(cv2, "face") and hasattr(cv2.face, "LBPHFaceRecognizer_create"):
                    self.lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()
                    if LBPH_MODEL_PATH.exists() and LABELS_MAP_PATH.exists():
                        self.lbph_recognizer.read(str(LBPH_MODEL_PATH))
                        with open(LABELS_MAP_PATH, "r", encoding="utf-8") as f:
                            raw_map = json.load(f)
                            self.labels_to_id = {int(k): v for k, v in raw_map.items()}
                            self.id_to_labels = {v: int(k) for k, v in raw_map.items()}
                        return True
                return False
        except Exception as e:
            print(f"Error loading face model: {e}")
            return False

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detects faces in a BGR image frame using Haar Cascade.
        Returns list of bounding boxes (x, y, w, h).
        """
        if frame is None or frame.size == 0:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Contrast adjustment for varied lighting conditions
        gray = cv2.equalizeHist(gray)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.15,
            minNeighbors=5,
            minSize=(80, 80),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def save_face_sample(
        self,
        frame: np.ndarray,
        box: Tuple[int, int, int, int],
        person_id: str,
        sample_index: int
    ) -> Optional[Path]:
        """
        Crops face from frame with slight padding, normalizes, and saves to dataset folder.
        """
        x, y, w, h = box
        h_frame, w_frame = frame.shape[:2]

        # Add 10% margin around face
        margin_x = int(w * 0.1)
        margin_y = int(h * 0.1)
        x1 = max(0, x - margin_x)
        y1 = max(0, y - margin_y)
        x2 = min(w_frame, x + w + margin_x)
        y2 = min(h_frame, y + h + margin_y)

        face_roi = frame[y1:y2, x1:x2]
        if face_roi.size == 0:
            return None

        # Person specific directory
        person_dir = DATASET_DIR / person_id
        person_dir.mkdir(parents=True, exist_ok=True)

        # Standardize face crop dimensions (250x250)
        face_resized = cv2.resize(face_roi, (250, 250), interpolation=cv2.INTER_AREA)
        file_path = person_dir / f"sample_{sample_index:03d}.jpg"
        cv2.imwrite(str(file_path), face_resized)
        return file_path

    def delete_person_face_data(self, person_id: str) -> None:
        """Removes the stored dataset samples of a specific person and retrains the model."""
        person_dir = DATASET_DIR / person_id
        if person_dir.exists():
            shutil.rmtree(person_dir, ignore_errors=True)
        # Retrain the model so the deleted person is immediately removed from memory
        self.train_model()

    def train_model(self) -> Tuple[bool, str, int]:
        """
        Scans all images in the `dataset/` directory and trains or builds encodings.
        Returns (success, message, total_persons_trained).
        """
        if not DATASET_DIR.exists():
            return False, "Dataset directory does not exist.", 0

        person_folders = [d for d in DATASET_DIR.iterdir() if d.is_dir()]
        if not person_folders:
            # Clean up existing trained models if dataset is empty
            if LBPH_MODEL_PATH.exists():
                LBPH_MODEL_PATH.unlink(missing_ok=True)
            if LABELS_MAP_PATH.exists():
                LABELS_MAP_PATH.unlink(missing_ok=True)
            if DLIB_ENCODINGS_PATH.exists():
                DLIB_ENCODINGS_PATH.unlink(missing_ok=True)
            self.labels_to_id.clear()
            self.id_to_labels.clear()
            self.dlib_known_encodings.clear()
            self.dlib_known_ids.clear()
            return True, "Dataset is empty. Recognition model cleared.", 0

        if self.use_dlib:
            return self._train_dlib(person_folders)
        else:
            return self._train_lbph(person_folders)

    def _train_dlib(self, person_folders: List[Path]) -> Tuple[bool, str, int]:
        """Trains using dlib 128D face encodings."""
        all_encodings = []
        all_ids = []

        for person_folder in person_folders:
            person_id = person_folder.name
            image_paths = list(person_folder.glob("*.jpg")) + list(person_folder.glob("*.png"))

            for img_path in image_paths:
                image = face_recognition.load_image_file(str(img_path))
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    all_encodings.append(encodings[0])
                    all_ids.append(person_id)

        if not all_encodings:
            return False, "No valid faces could be encoded from the dataset images.", 0

        data = {"encodings": all_encodings, "ids": all_ids}
        with open(DLIB_ENCODINGS_PATH, "wb") as f:
            pickle.dump(data, f)

        self.dlib_known_encodings = all_encodings
        self.dlib_known_ids = all_ids
        total_unique = len(set(all_ids))
        return True, f"Successfully trained {len(all_encodings)} face encodings for {total_unique} people.", total_unique

    def _train_lbph(self, person_folders: List[Path]) -> Tuple[bool, str, int]:
        """Trains using OpenCV's LBPH Face Recognizer."""
        faces = []
        labels = []
        new_labels_to_id = {}
        new_id_to_labels = {}
        current_label_id = 1

        for person_folder in person_folders:
            person_id = person_folder.name
            image_paths = list(person_folder.glob("*.jpg")) + list(person_folder.glob("*.png"))

            if not image_paths:
                continue

            new_labels_to_id[current_label_id] = person_id
            new_id_to_labels[person_id] = current_label_id

            for img_path in image_paths:
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                # Resize to standard size for LBPH consistency
                img_resized = cv2.resize(img, (200, 200), interpolation=cv2.INTER_AREA)
                img_eq = cv2.equalizeHist(img_resized)
                faces.append(img_eq)
                labels.append(current_label_id)

            current_label_id += 1

        if not faces:
            return False, "No valid face images found in the dataset to train.", 0

        recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
        recognizer.train(faces, np.array(labels, dtype=np.int32))

        # Save model and label mapping
        recognizer.write(str(LBPH_MODEL_PATH))
        with open(LABELS_MAP_PATH, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in new_labels_to_id.items()}, f, indent=2)

        self.lbph_recognizer = recognizer
        self.labels_to_id = new_labels_to_id
        self.id_to_labels = new_id_to_labels
        total_unique = len(new_labels_to_id)

        return True, f"Trained {len(faces)} face samples across {total_unique} registered individuals.", total_unique

    def recognize_face(
        self,
        frame: np.ndarray,
        box: Tuple[int, int, int, int]
    ) -> Tuple[Optional[str], float, bool]:
        """
        Recognizes the face within the bounding box.
        Returns:
            (person_id, confidence_percentage, is_known)
        """
        if not self.is_model_trained():
            return None, 0.0, False

        x, y, w, h = box

        if self.use_dlib:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Dlib format is (top, right, bottom, left)
            top = max(0, y)
            right = min(frame.shape[1], x + w)
            bottom = min(frame.shape[0], y + h)
            left = max(0, x)

            encodings = face_recognition.face_encodings(rgb, [(top, right, bottom, left)])
            if not encodings or len(self.dlib_known_encodings) == 0:
                return None, 0.0, False

            face_encoding = encodings[0]
            distances = face_recognition.face_distance(self.dlib_known_encodings, face_encoding)
            min_dist_idx = np.argmin(distances)
            min_dist = distances[min_dist_idx]

            # Dlib tolerance 0.5 (smaller is more accurate)
            if min_dist < 0.52:
                matched_id = self.dlib_known_ids[min_dist_idx]
                confidence = max(0.0, min(100.0, (1.0 - min_dist) * 100))
                return matched_id, confidence, True
            else:
                return None, 0.0, False
        else:
            if self.lbph_recognizer is None:
                return None, 0.0, False

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            face_roi = gray[y:y+h, x:x+w]
            if face_roi.size == 0:
                return None, 0.0, False

            face_resized = cv2.resize(face_roi, (200, 200), interpolation=cv2.INTER_AREA)
            face_eq = cv2.equalizeHist(face_resized)

            label_id, distance = self.lbph_recognizer.predict(face_eq)

            # In LBPH, 0 = exact match; values < self.lbph_threshold are considered a match
            if distance < self.lbph_threshold:
                person_id = self.labels_to_id.get(label_id)
                # Map distance to confidence percentage (0 dist -> 100%, 70 dist -> ~60%)
                conf_pct = max(10.0, min(99.0, 100.0 - (distance * 0.7)))
                return person_id, conf_pct, True
            else:
                return None, 0.0, False

    def draw_hud_box(
        self,
        frame: np.ndarray,
        box: Tuple[int, int, int, int],
        title: str,
        subtitle: str = "",
        is_known: bool = True,
        is_already_marked: bool = False
    ) -> None:
        """
        Draws a modern HUD bounding box with corner accents and a rounded info badge.
        """
        x, y, w, h = box

        # Select color palette:
        # Green (Known & Not yet marked)
        # Sky Blue / Cyan (Known & Already marked today)
        # Red / Crimson (Unknown)
        if not is_known:
            color = (55, 55, 235)       # Red
            badge_bg = (35, 35, 180)
        elif is_already_marked:
            color = (235, 175, 45)      # Cyan / Teal
            badge_bg = (180, 120, 20)
        else:
            color = (65, 215, 95)       # Emerald Green
            badge_bg = (30, 150, 60)

        # Draw semi-transparent bounding box outline
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # Draw tech corner brackets
        corner_len = min(22, w // 4, h // 4)
        thickness = 3
        # Top-left
        cv2.line(frame, (x, y), (x + corner_len, y), color, thickness)
        cv2.line(frame, (x, y), (x, y + corner_len), color, thickness)
        # Top-right
        cv2.line(frame, (x + w, y), (x + w - corner_len, y), color, thickness)
        cv2.line(frame, (x + w, y), (x + w, y + corner_len), color, thickness)
        # Bottom-left
        cv2.line(frame, (x, y + h), (x + corner_len, y + h), color, thickness)
        cv2.line(frame, (x, y + h), (x, y + h - corner_len), color, thickness)
        # Bottom-right
        cv2.line(frame, (x + w, y + h), (x + w - corner_len, y + h), color, thickness)
        cv2.line(frame, (x + w, y + h), (x + w, y + h - corner_len), color, thickness)

        # Prepare badge text
        font = cv2.FONT_HERSHEY_DUPLEX
        font_scale = 0.55
        badge_h = 32 if subtitle else 24

        # Background pill above or below box
        badge_y1 = max(0, y - badge_h - 6)
        badge_y2 = badge_y1 + badge_h
        text_size = cv2.getTextSize(title, font, font_scale, 1)[0]
        badge_w = max(w, text_size[0] + 20)

        # Draw filled badge header
        cv2.rectangle(frame, (x, badge_y1), (x + badge_w, badge_y2), badge_bg, -1)
        cv2.rectangle(frame, (x, badge_y1), (x + badge_w, badge_y2), color, 1)

        # Draw Title
        cv2.putText(frame, title, (x + 8, badge_y1 + 18), font, font_scale, (255, 255, 255), 1, cv2.LINE_AA)

        # Draw Subtitle if present
        if subtitle:
            sub_font_scale = 0.42
            cv2.putText(frame, subtitle, (x + 8, badge_y1 + 29), font, sub_font_scale, (220, 220, 220), 1, cv2.LINE_AA)


# Global singleton instance for the application
face_manager = FaceRecognizerManager()
