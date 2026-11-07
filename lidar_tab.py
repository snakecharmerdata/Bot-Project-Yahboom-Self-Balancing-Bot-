"""LiDAR tab: live top-down radar view from the T-mini Plus (see lidar/tmini.py)."""
import math
import time
import tkinter as tk
from tkinter import ttk

from lidar.guard import CONE_HALF_DEG, HEADING

BG, PANEL, FG, DIM = "#1e1e1e", "#2a2a2a", "#dddddd", "#888888"
OK, WARN, BAD = "#66cc66", "#e6b84d", "#e66666"
RANGES_M = [1, 2, 4, 8, 12]   # zoom levels (radius of the view, metres)
CLOSE_MM = 400                # points nearer than this are drawn red
REFRESH_MS = 100


class LidarTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.lidar = app.lidar
        self.range_idx = 2
        self.last_scans = 0
        self.rate = 0.0
        self._rate_t = time.time()

        self.canvas = tk.Canvas(self, bg="#111", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom(-1))
        self.canvas.bind("<Button-5>", lambda e: self.zoom(1))

        side = tk.Frame(self, bg=PANEL, width=250)
        side.pack(side="right", fill="y", padx=(0, 8), pady=8)
        side.pack_propagate(False)
        tk.Label(side, text="LIDAR", bg=PANEL, fg=DIM, font=("Sans", 9, "bold")).pack(
            anchor="w", padx=12, pady=(12, 2))
        self.status = tk.Label(side, bg=PANEL, fg=FG, font=("Sans", 11), anchor="w",
                               wraplength=230, justify="left")
        self.status.pack(fill="x", padx=12)

        tk.Label(side, text="NEAREST OBJECT", bg=PANEL, fg=DIM, font=("Sans", 9, "bold")).pack(
            anchor="w", padx=12, pady=(18, 2))
        self.nearest = tk.Label(side, bg=PANEL, fg=FG, font=("Sans", 20, "bold"), anchor="w")
        self.nearest.pack(fill="x", padx=12)
        self.nearest_dir = tk.Label(side, bg=PANEL, fg=DIM, font=("Sans", 10), anchor="w")
        self.nearest_dir.pack(fill="x", padx=12)

        tk.Label(side, text="VIEW", bg=PANEL, fg=DIM, font=("Sans", 9, "bold")).pack(
            anchor="w", padx=12, pady=(18, 4))
        zoom = tk.Frame(side, bg=PANEL)
        zoom.pack(fill="x", padx=12)
        ttk.Button(zoom, text="➖ Zoom out", command=lambda: self.zoom(1)).pack(
            side="left", expand=True, fill="x")
        ttk.Button(zoom, text="➕ Zoom in", command=lambda: self.zoom(-1)).pack(
            side="left", expand=True, fill="x", padx=(4, 0))
        ttk.Button(side, text="↻ Rotate view 90°", command=self.rotate).pack(
            fill="x", padx=12, pady=(6, 0))
        tk.Label(side, bg=PANEL, fg=DIM, font=("Sans", 9), wraplength=230, justify="left",
                 text="Rotate until the side the bot faces is at the top. Mouse wheel zooms."
                 ).pack(anchor="w", padx=12, pady=(6, 0))

        tk.Label(side, text="OBSTACLE STOP", bg=PANEL, fg=DIM, font=("Sans", 9, "bold")).pack(
            anchor="w", padx=12, pady=(18, 2))
        self.guard_label = tk.Label(side, bg=PANEL, fg=FG, font=("Sans", 10), anchor="w",
                                    wraplength=230, justify="left")
        self.guard_label.pack(fill="x", padx=12)

        self.after(REFRESH_MS, self._refresh)

    def zoom(self, step):
        self.range_idx = min(max(self.range_idx + step, 0), len(RANGES_M) - 1)

    def _wheel(self, e):
        self.zoom(-1 if e.delta > 0 else 1)

    def rotate(self):
        s = self.app.settings
        s["lidar_rotation"] = (s["lidar_rotation"] + 90) % 360
        self.app.save_settings()

    def _refresh(self):
        if self.app.tabs.select() == str(self):
            self._draw()
        self.after(REFRESH_MS, self._refresh)

    def _draw(self):
        c = self.canvas
        w, h = max(c.winfo_width(), 1), max(c.winfo_height(), 1)
        cx, cy = w / 2, h / 2
        radius_px = min(w, h) / 2 - 20
        range_mm = RANGES_M[self.range_idx] * 1000
        scale = radius_px / range_mm
        c.delete("all")

        # range rings, every 1/4 of the view radius
        for k in range(1, 5):
            r = radius_px * k / 4
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#2c3a2c")
            c.create_text(cx + 4, cy - r + 2, text=f"{RANGES_M[self.range_idx] * k / 4:g} m",
                          fill="#557755", anchor="nw", font=("Sans", 8))
        c.create_line(cx, cy - radius_px, cx, cy + radius_px, fill="#22302a")
        c.create_line(cx - radius_px, cy, cx + radius_px, cy, fill="#22302a")
        c.create_text(cx, cy - radius_px - 10, text="▲ front", fill=DIM, font=("Sans", 9))

        # obstacle-stop zones in front and behind
        rotation = self.app.settings["lidar_rotation"]
        if self.app.settings["obstacle_stop"]:
            r = min(self.app.settings["obstacle_stop_mm"] * scale, radius_px)
            for heading in sorted(set(HEADING.values())):
                start = 90 - heading - CONE_HALF_DEG  # Tk angles: 0 = east, counter-clockwise
                c.create_arc(cx - r, cy - r, cx + r, cy + r, start=start,
                             extent=2 * CONE_HALF_DEG, style="pieslice", fill="#3a2222",
                             outline="#6a3333")

        scan = self.lidar.latest_scan()
        nearest = None
        for angle, dist, _ in scan:
            if dist > range_mm:
                continue
            a = math.radians(angle + rotation)
            x, y = cx + dist * scale * math.sin(a), cy - dist * scale * math.cos(a)
            color = BAD if dist < CLOSE_MM else "#5fd35f"
            c.create_rectangle(x - 1.5, y - 1.5, x + 1.5, y + 1.5, fill=color, outline="")
        for angle, dist, _ in scan:
            if nearest is None or dist < nearest[1]:
                nearest = (angle, dist)

        # the bot at the centre
        c.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill="#66ccff", outline="")
        c.create_polygon(cx, cy - 14, cx - 5, cy - 6, cx + 5, cy - 6, fill="#66ccff")

        now = time.time()
        if now - self._rate_t >= 1:
            self.rate = (self.lidar.scans - self.last_scans) / (now - self._rate_t)
            self.last_scans, self._rate_t = self.lidar.scans, now
        if self.lidar.connected and scan:
            self.status.configure(text=f"● Scanning  {self.rate:.1f} rotations/s\n"
                                       f"{len(scan)} points per rotation", fg=OK)
        elif self.lidar.connected:
            self.status.configure(text="● Starting…", fg=WARN)
        else:
            self.status.configure(text=f"● Not connected\n{self.lidar.error}", fg=BAD)

        if nearest:
            self.nearest.configure(text=f"{nearest[1] / 1000:.2f} m",
                                   fg=BAD if nearest[1] < CLOSE_MM else FG)
            bearing = (nearest[0] + rotation) % 360
            names = ["front", "front-right", "right", "back-right", "back", "back-left",
                     "left", "front-left"]
            self.nearest_dir.configure(text=f"{names[int((bearing + 22.5) // 45) % 8]} "
                                            f"({bearing:.0f}°)")
        else:
            self.nearest.configure(text="—", fg=DIM)
            self.nearest_dir.configure(text="")

        g = self.app.guard
        if not g.enabled:
            self.guard_label.configure(text="Off (switch on in the Drive tab)", fg=DIM)
        elif self.lidar.scan_age() > 0.6:
            self.guard_label.configure(text="On, but no LiDAR data — NOT protecting", fg=BAD)
        else:
            self.guard_label.configure(
                text=f"On: stops within {self.app.settings['obstacle_stop_mm'] / 1000:.2f} m "
                     f"(red zones)" + (f"\n⛔ {g.blocked}" if g.blocked else ""),
                fg=WARN if g.blocked else OK)
