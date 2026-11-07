"""Drive tab: manual control of the bot over Bluetooth.

Hold a button or key to move; release to stop. While something is held the
command is renewed every RENEW_MS, so the bot keeps going (see bot/drive.py).
"""
import io
import time
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

RENEW_MS = 100
# Linux key autorepeat sends release+press pairs while a key is held; wait this
# long after a release before treating the key as really let go.
RELEASE_GRACE_MS = 80

KEYS = {
    "Up": "forward", "w": "forward",
    "Down": "backward", "s": "backward",
    "Left": "left", "a": "left",
    "Right": "right", "d": "right",
    "q": "spin_left", "e": "spin_right",
}
LABELS = {"stop": "⏹  STOP", "forward": "⬆  FORWARD", "backward": "⬇  BACKWARD",
          "left": "⬅  LEFT", "right": "➡  RIGHT", "spin_left": "⟲  SPIN LEFT",
          "spin_right": "⟳  SPIN RIGHT"}

BG, PANEL, FG, DIM = "#1e1e1e", "#2a2a2a", "#dddddd", "#888888"
OK, WARN, BAD = "#66cc66", "#e6b84d", "#e66666"


class DriveTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.drive = app.drive
        self.held = None          # action currently held by mouse or key
        self.manual_until = 0.0   # autopilot stays quiet until this time
        self._release_job = None
        self.shown_id = -1
        self.photo = None

        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=(12, 6))
        self.conn_label = tk.Label(top, bg=BG, fg=FG, font=("Sans", 12), anchor="w")
        self.conn_label.pack(side="left", fill="x", expand=True)
        self.conn_btn = ttk.Button(top, text="🔌 Connect to bot", command=self.toggle_connect)
        self.conn_btn.pack(side="right")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.video = tk.Label(body, bg="black", fg="#aaa", text="Waiting for camera…",
                              font=("Sans", 13))
        self.video.pack(side="left", fill="both", expand=True)

        side = tk.Frame(body, bg=BG, width=330)
        side.pack(side="right", fill="y", padx=(12, 0))
        side.pack_propagate(False)
        tk.Label(side, bg=BG, fg=DIM, font=("Sans", 9), justify="left", anchor="w",
                 wraplength=320,
                 text="Before driving: switch the bot to 1. Standard Mode, stand it up and press "
                      "its start button so it balances.\n\nKeys: arrows / WASD to drive, Q / E to "
                      "spin, Space or Esc to STOP. Hold to move, release to stop.").pack(
            fill="x", pady=(0, 8))

        pad = tk.Frame(side, bg=BG)
        pad.pack(expand=True)
        btn = dict(font=("Sans", 16, "bold"), width=4, height=2, bg=PANEL, fg=FG,
                   activebackground="#3a3a3a", activeforeground=FG, relief="flat")
        layout = [("⟲", "spin_left", 0, 0), ("⬆", "forward", 0, 1), ("⟳", "spin_right", 0, 2),
                  ("⬅", "left", 1, 0), ("➡", "right", 1, 2), ("⬇", "backward", 2, 1)]
        for text, action, r, c in layout:
            b = tk.Button(pad, text=text, **btn)
            b.grid(row=r, column=c, padx=6, pady=6)
            b.bind("<ButtonPress-1>", lambda e, a=action: self.hold(a))
            b.bind("<ButtonRelease-1>", lambda e: self.release())
        tk.Button(pad, text="STOP", command=self.emergency_stop, font=("Sans", 16, "bold"),
                  width=4, height=2, bg="#a33", fg="white", activebackground="#c44",
                  activeforeground="white", relief="flat").grid(row=1, column=1, padx=6, pady=6)

        self.sent_label = tk.Label(side, bg=BG, fg=DIM, font=("Sans", 16, "bold"))
        self.sent_label.pack(pady=(8, 8))

        self.guard_var = tk.BooleanVar(value=app.settings["obstacle_stop"])
        tk.Checkbutton(side, text="Obstacle stop (LiDAR)", variable=self.guard_var,
                       command=self._guard_toggled, bg=BG, fg=FG, selectcolor="#3a3a3a",
                       activebackground=BG, activeforeground=FG, font=("Sans", 11, "bold"),
                       anchor="w").pack(fill="x")
        self.guard_label = tk.Label(side, bg=BG, fg=DIM, font=("Sans", 10), anchor="w",
                                    wraplength=320, justify="left")
        self.guard_label.pack(fill="x", pady=(0, 8))

        root = app
        root.bind_all("<KeyPress>", self._key_down, add="+")
        root.bind_all("<KeyRelease>", self._key_up, add="+")

        self.after(RENEW_MS, self._tick)
        self.after(40, self._update_video)

    # ----- live camera -----
    def _update_video(self):
        jpeg, frame_id = self.app.stream.latest()
        if jpeg and frame_id != self.shown_id and self._visible():
            self.shown_id = frame_id
            try:
                img = Image.open(io.BytesIO(jpeg))
                w, h = max(self.video.winfo_width(), 1), max(self.video.winfo_height(), 1)
                scale = min(w / img.width, h / img.height)
                img = img.resize((max(int(img.width * scale), 1), max(int(img.height * scale), 1)))
                self.photo = ImageTk.PhotoImage(img)
                self.video.configure(image=self.photo, text="")
            except Exception:
                pass  # skip a corrupt frame
        self.after(40, self._update_video)

    def _guard_toggled(self):
        self.app.settings["obstacle_stop"] = self.guard_var.get()
        self.app.save_settings()

    # ----- connection -----
    def toggle_connect(self):
        if self.drive.enabled:
            self.emergency_stop()
            self.drive.disconnect()
        else:
            self.drive.connect()

    # ----- holding / releasing -----
    def hold(self, action):
        if self._release_job:
            self.after_cancel(self._release_job)
            self._release_job = None
        self.held = action
        self._renew()

    def release(self):
        self.held = None
        self.drive.stop()

    def emergency_stop(self):
        self.held = None
        self.drive.stop()
        self.app.disable_autopilot_driving()

    def _renew(self):
        if self.held:
            self.drive.send(self.held)
            self.manual_until = time.time() + 0.3

    def _visible(self):
        return self.app.tabs.select() == str(self)

    def _key_down(self, e):
        if e.keysym in ("space", "Escape"):
            self.emergency_stop()
            return
        if not self._visible():
            return
        action = KEYS.get(e.keysym.lower() if len(e.keysym) == 1 else e.keysym)
        if action:
            self.hold(action)

    def _key_up(self, e):
        action = KEYS.get(e.keysym.lower() if len(e.keysym) == 1 else e.keysym)
        if action and action == self.held:
            if self._release_job:
                self.after_cancel(self._release_job)
            self._release_job = self.after(RELEASE_GRACE_MS, self._really_released)

    def _really_released(self):
        self._release_job = None
        self.release()

    # ----- periodic refresh -----
    def _tick(self):
        self._renew()
        d = self.drive
        color = OK if d.connected else (WARN if d.enabled else DIM)
        self.conn_label.configure(text=f"● {d.status}", fg=color)
        self.conn_btn.configure(text="Disconnect" if d.enabled else "🔌 Connect to bot")
        sent = d.last_sent if d.connected else "stop"
        self.sent_label.configure(text=LABELS[sent] if d.connected else "—",
                                  fg=OK if sent != "stop" else DIM)
        g = self.app.guard
        if g.blocked and self.held:
            self.guard_label.configure(text=f"⛔ {g.blocked} — stopped", fg=BAD)
        elif not g.enabled:
            self.guard_label.configure(text="Off: the bot can drive into things.", fg=WARN)
        elif self.app.lidar.scan_age() > 0.6:
            self.guard_label.configure(text="No LiDAR data — not protecting.", fg=WARN)
        else:
            self.guard_label.configure(
                text=f"On: stops if something is within "
                     f"{self.app.settings['obstacle_stop_mm'] / 1000:.2f} m ahead/behind.", fg=OK)
        self.after(RENEW_MS, self._tick)
