"""Face recognition mode: finds faces, names the ones it has been taught, and
turns the bot to keep the chosen person centred."""
import os

import cv2
import numpy as np

from .common import Command, put_label, steer

# Cosine-similarity threshold recommended for the SFace model.
MATCH_THRESHOLD = 0.363


class FaceMode:
    def __init__(self, models_dir, db_path):
        self.det = cv2.FaceDetectorYN.create(
            os.path.join(models_dir, "face_detection_yunet_2023mar.onnx"), "", (320, 240), 0.8)
        self.rec = cv2.FaceRecognizerSF.create(
            os.path.join(models_dir, "face_recognition_sface_2021dec.onnx"), "")
        self.db_path = db_path
        self.names = []
        self.feats = np.zeros((0, 128), np.float32)
        self.message = ""
        self._pending_enroll = None
        if os.path.exists(db_path):
            data = np.load(db_path)
            self.names, self.feats = list(data["names"]), data["feats"]
        self._update_message()

    # Requests from the UI (run on the vision worker thread)
    def enroll(self, name):
        self._pending_enroll = name

    def forget_all(self):
        self.names, self.feats = [], np.zeros((0, 128), np.float32)
        self._save()
        self.message = "Forgot all faces."

    def _save(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        np.savez(self.db_path, names=np.array(self.names), feats=self.feats)

    def _update_message(self):
        people = sorted(set(self.names))
        self.message = f"Knows: {', '.join(people)}" if people else "No faces enrolled yet."

    def _feature(self, frame, face):
        f = self.rec.feature(self.rec.alignCrop(frame, face)).flatten()
        return f / (np.linalg.norm(f) + 1e-9)

    def _identify(self, feat):
        if not len(self.names):
            return None, 0.0
        sims = self.feats @ feat
        best = int(np.argmax(sims))
        return (self.names[best], float(sims[best])) if sims[best] >= MATCH_THRESHOLD \
            else (None, float(sims[best]))

    def process(self, frame, canvas, s):
        h, w = frame.shape[:2]
        self.det.setInputSize((w, h))
        _, faces = self.det.detect(frame)
        faces = [] if faces is None else list(faces)

        if self._pending_enroll:
            name, self._pending_enroll = self._pending_enroll, None
            if faces:
                biggest = max(faces, key=lambda f: f[2] * f[3])
                self.names.append(name)
                self.feats = np.vstack([self.feats, self._feature(frame, biggest)])
                self._save()
                self._update_message()
                self.message = f"Enrolled {name}. " + self.message
            else:
                self.message = "No face in view to enroll — face the camera and try again."

        people = []
        for f in faces:
            name, sim = self._identify(self._feature(frame, f))
            people.append((f, name))
            x, y, bw, bh = (f[:4] * s).astype(int)
            color = (80, 220, 80) if name else (60, 180, 255)
            cv2.rectangle(canvas, (x, y), (x + bw, y + bh), color, 2)
            put_label(canvas, f"{name} ({sim:.2f})" if name else "Unknown", (x, max(y - 8, 18)), color)

        if not people:
            return Command(reason="No face in view")
        known = [p for p in people if p[1]]
        face, name = max(known or people, key=lambda p: p[0][2] * p[0][3])
        offset = (face[0] + face[2] / 2) / w * 2 - 1
        return steer(offset, reason=f"Looking at {name or 'unknown person'}")
