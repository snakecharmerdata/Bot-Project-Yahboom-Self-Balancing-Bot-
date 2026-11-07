"""Hand-gesture mode: MediaPipe recognises a hand gesture, which maps to a drive command."""
import os
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from .common import Command, put_label

# MediaPipe gesture name -> (command, description shown in the UI legend)
GESTURES = {
    "Thumb_Up": (Command("forward", 0.5, 0.0), "👍  Thumb up → forward"),
    "Thumb_Down": (Command("backward", -0.5, 0.0), "👎  Thumb down → backward"),
    "Victory": (Command("left", 0.0, -0.6), "✌  Victory → turn left"),
    "Pointing_Up": (Command("right", 0.0, 0.6), "☝  Pointing up → turn right"),
    "Open_Palm": (Command("stop"), "✋  Open palm → stop"),
    "Closed_Fist": (Command("stop"), "✊  Fist → stop"),
}
STABLE_FRAMES = 2      # same gesture this many frames in a row before acting
HAND_TIMEOUT_S = 1.0   # stop if no hand has been seen for this long

HAND_CONNECTIONS = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
                    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15),
                    (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]


class GestureMode:
    def __init__(self, models_dir):
        options = vision.GestureRecognizerOptions(
            base_options=BaseOptions(
                model_asset_path=os.path.join(models_dir, "gesture_recognizer.task")),
            num_hands=1)
        self.recognizer = vision.GestureRecognizer.create_from_options(options)
        self.message = "Show a gesture to the camera."
        self.candidate, self.count = None, 0
        self.active = None
        self.last_hand = 0.0

    def close(self):
        self.recognizer.close()

    def process(self, frame, canvas, s):
        h, w = frame.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        result = self.recognizer.recognize(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))

        gesture = None
        if result.hand_landmarks:
            self.last_hand = time.time()
            pts = [(int(p.x * w * s), int(p.y * h * s)) for p in result.hand_landmarks[0]]
            for a, b in HAND_CONNECTIONS:
                cv2.line(canvas, pts[a], pts[b], (80, 220, 80), 2)
            for p in pts:
                cv2.circle(canvas, p, 3, (255, 255, 255), -1)
            if result.gestures and result.gestures[0]:
                top = result.gestures[0][0]
                if top.category_name in GESTURES and top.score > 0.5:
                    gesture = top.category_name
                label = top.category_name if top.category_name != "None" else "hand"
                put_label(canvas, f"{label} ({top.score:.2f})", (12, 30), (80, 220, 80))

        # Only switch command once the same gesture has been seen a few frames running.
        if gesture == self.candidate:
            self.count += 1
        else:
            self.candidate, self.count = gesture, 1
        if gesture and self.count >= STABLE_FRAMES:
            self.active = gesture

        if time.time() - self.last_hand > HAND_TIMEOUT_S:
            self.active = None
        if not self.active:
            return Command(reason="No gesture" if not result.hand_landmarks else "Hold the gesture steady")
        cmd, desc = GESTURES[self.active]
        return Command(cmd.action, cmd.speed, cmd.turn, desc.split("  ", 1)[1])
