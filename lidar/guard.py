"""Obstacle stop: turns drive commands into STOP when the LiDAR sees something
too close in the direction of travel. Spinning on the spot is always allowed,
so the bot can turn away from an obstacle."""

CONE_HALF_DEG = 35   # how wide "ahead" / "behind" is, either side of straight
MIN_VALID_MM = 80    # nearer readings are ignored (the bot's own frame, dust on the lens)
STALE_S = 0.6        # LiDAR data older than this is not trusted

# Direction each command moves the bot in (0 = front). The turn commands may
# move forward while turning, so they are checked like forward.
HEADING = {"forward": 0, "left": 0, "right": 0, "backward": 180}


class ObstacleGuard:
    def __init__(self, lidar, settings):
        self.lidar = lidar
        self.settings = settings
        self.blocked = ""   # why the last command was stopped, or ""
        self.state = ""     # short description for the UI

    @property
    def enabled(self):
        return self.settings["obstacle_stop"]

    def nearest_in_cone(self, heading):
        rotation = self.settings["lidar_rotation"]
        nearest = None
        for angle, dist, _ in self.lidar.latest_scan():
            if dist < MIN_VALID_MM:
                continue
            off = (angle + rotation - heading + 180) % 360 - 180
            if abs(off) <= CONE_HALF_DEG and (nearest is None or dist < nearest):
                nearest = dist
        return nearest

    def filter(self, action):
        """Return the action to actually send (the same one, or "stop")."""
        if not self.enabled:
            self.state, self.blocked = "off", ""
            return action
        if self.lidar.scan_age() > STALE_S:
            self.state, self.blocked = "no LiDAR data — not protecting", ""
            return action
        self.state = "on"
        if action not in HEADING:
            self.blocked = ""
            return action
        nearest = self.nearest_in_cone(HEADING[action])
        if nearest is not None and nearest < self.settings["obstacle_stop_mm"]:
            where = "behind" if HEADING[action] == 180 else "ahead"
            self.blocked = f"Obstacle {nearest / 1000:.2f} m {where}"
            return "stop"
        self.blocked = ""
        return action
