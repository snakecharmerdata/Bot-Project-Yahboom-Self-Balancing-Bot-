"""Shared types and helpers for the vision modes."""
from dataclasses import dataclass

import cv2

# How far off-centre (as a fraction of half the image width) a target may be
# before the bot turns towards it.
DEAD_ZONE = 0.15


@dataclass
class Command:
    action: str = "stop"  # stop | forward | backward | left | right
    speed: float = 0.0    # -1 (backward) .. 1 (forward)
    turn: float = 0.0     # -1 (left) .. 1 (right)
    reason: str = ""


def steer(offset, speed=0.0, reason=""):
    """Build a Command that turns towards a target.

    offset: target's horizontal position, -1 (left edge) .. 1 (right edge).
    speed:  forward/backward speed to use once the target is centred.
    """
    if abs(offset) > DEAD_ZONE:
        turn = max(-1.0, min(1.0, offset))
        return Command("left" if offset < 0 else "right", speed, turn, reason)
    if speed > 0:
        return Command("forward", speed, 0.0, reason)
    if speed < 0:
        return Command("backward", speed, 0.0, reason)
    return Command("stop", 0.0, 0.0, reason)


def put_label(img, text, org, color=(255, 255, 255)):
    """Outlined text that stays readable on any background."""
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)
