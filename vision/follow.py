"""Follow-object mode: the user drags a box around an object, and the bot turns
towards it and drives to keep it at the size it had when selected."""
import cv2

from .common import Command, put_label, steer

LOST_FRAMES_LIMIT = 10  # give up on the target after this many failed frames
FOLLOW_SPEED = 0.5


class FollowMode:
    def __init__(self):
        self.tracker = None
        self.ref_area = None
        self.lost = 0
        self.message = "Drag a box around an object on the video."
        self._pending_box = None

    # Requests from the UI (run on the vision worker thread)
    def select(self, box):
        self._pending_box = box

    def clear(self):
        self.tracker = None
        self.message = "Target cleared. Drag a box around an object."

    def process(self, frame, canvas, s):
        h, w = frame.shape[:2]
        if self._pending_box:
            x, y, bw, bh = self._pending_box
            self._pending_box = None
            if bw >= 8 and bh >= 8:
                self.tracker = cv2.TrackerCSRT_create()
                self.tracker.init(frame, (x, y, bw, bh))
                self.ref_area = bw * bh
                self.lost = 0
                self.message = "Following target. Move it and watch the command."

        if self.tracker is None:
            put_label(canvas, "Drag a box around an object to follow it", (12, 30))
            return Command(reason="No target selected")

        ok, box = self.tracker.update(frame)
        if not ok:
            self.lost += 1
            put_label(canvas, "Target lost…", (12, 30), (60, 180, 255))
            if self.lost > LOST_FRAMES_LIMIT:
                self.tracker = None
                self.message = "Target lost. Drag a new box to follow something."
            return Command(reason="Target lost")

        self.lost = 0
        x, y, bw, bh = box
        cv2.rectangle(canvas, (int(x * s), int(y * s)), (int((x + bw) * s), int((y + bh) * s)),
                      (80, 220, 80), 2)
        offset = (x + bw / 2) / w * 2 - 1
        ratio = bw * bh / self.ref_area
        if ratio < 0.7:
            speed, reason = FOLLOW_SPEED, "Target getting further away"
        elif ratio > 1.4:
            speed, reason = -FOLLOW_SPEED, "Target too close"
        else:
            speed, reason = 0.0, "Target at the right distance"
        put_label(canvas, f"size {ratio:.2f}x", (int(x * s), max(int(y * s) - 8, 18)), (80, 220, 80))
        return steer(offset, speed, reason)
