"""Autopilot tab: runs a vision mode on the live camera and shows the drive
command it produces. All model work happens on one background worker thread."""
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import simpledialog, ttk

from PIL import Image, ImageTk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(APP_DIR, "models")
FACES_DB = os.path.join(APP_DIR, "faces_db", "known_faces.npz")
SCALE = 2  # annotations are drawn on a 2x upscaled frame so text stays crisp

COMMAND_TEXT = {"stop": "⏹  STOP", "forward": "⬆  FORWARD", "backward": "⬇  BACKWARD",
                "left": "⬅  TURN LEFT", "right": "➡  TURN RIGHT"}
COMMAND_COLOR = {"stop": "#e6b84d", "forward": "#66cc66", "backward": "#66cc66",
                 "left": "#66ccff", "right": "#66ccff"}

BG, PANEL, FG, DIM = "#1e1e1e", "#2a2a2a", "#dddddd", "#888888"


class AutopilotTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
            from vision.common import Command
            from vision.gestures import GESTURES
        except ImportError as e:
            tk.Label(self, bg=BG, fg="#e66666", font=("Sans", 12), justify="center",
                     text=f"Autopilot needs the project's Python environment.\n\n"
                          f"Start the app with:  .venv/bin/python main.py\n\n({e})").pack(expand=True)
            return
        self.Command = Command
        self.drive = app.drive
        self.drive_var = tk.BooleanVar(value=False)
        self.drive_enabled = False  # plain copy of drive_var for the worker thread
        self.drive_var.trace_add("write", self._drive_toggled)
        self.mode_key = "off"
        self.requests = queue.Queue()
        self.lock = threading.Lock()
        self.output = None     # (rgb image, command, frame id)
        self.shown_id = -1
        self.mode_message = ""
        self.status_text = "Loading vision models…"
        self.photo = None
        self.view = None       # (offset x, offset y, displayed w, displayed h, frame w, frame h)
        self.drag_start = None

        self.canvas = tk.Canvas(self, bg="black", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        self.canvas.bind("<ButtonPress-1>", self._drag_begin)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._drag_end)

        side = tk.Frame(self, bg=PANEL, width=290)
        side.pack(side="right", fill="y", padx=(0, 8), pady=8)
        side.pack_propagate(False)

        tk.Label(side, text="MODE", bg=PANEL, fg=DIM, font=("Sans", 9, "bold")).pack(
            anchor="w", padx=12, pady=(12, 4))
        self.mode_var = tk.StringVar(value="off")
        for key, text in (("off", "Off"), ("face", "🙂  Face recognition"),
                          ("follow", "🎯  Follow object"), ("gesture", "✋  Hand gestures")):
            tk.Radiobutton(side, text=text, value=key, variable=self.mode_var,
                           command=self._mode_changed, bg=PANEL, fg=FG, selectcolor="#3a3a3a",
                           activebackground=PANEL, activeforeground=FG, font=("Sans", 11),
                           anchor="w").pack(fill="x", padx=12)

        self.controls = tk.Frame(side, bg=PANEL)
        self.controls.pack(fill="x", padx=12, pady=(10, 0))
        self.mode_controls = {
            "face": self._face_controls(),
            "follow": self._follow_controls(),
            "gesture": self._gesture_controls(GESTURES),
        }
        self.mode_msg = tk.Label(side, bg=PANEL, fg=DIM, font=("Sans", 9), wraplength=260,
                                 justify="left")
        self.mode_msg.pack(anchor="w", padx=12, pady=(6, 0))

        tk.Label(side, text="COMMAND", bg=PANEL, fg=DIM, font=("Sans", 9, "bold")).pack(
            anchor="w", padx=12, pady=(18, 2))
        self.cmd_label = tk.Label(side, text="—", bg=PANEL, fg=FG, font=("Sans", 20, "bold"),
                                  anchor="w")
        self.cmd_label.pack(fill="x", padx=12)
        self.reason_label = tk.Label(side, bg=PANEL, fg=FG, font=("Sans", 10), anchor="w",
                                     wraplength=260, justify="left")
        self.reason_label.pack(fill="x", padx=12)
        motors = tk.Frame(side, bg=PANEL)
        motors.pack(side="bottom", fill="x", padx=12, pady=12)
        tk.Checkbutton(motors, text="Let autopilot drive the bot", variable=self.drive_var,
                       bg=PANEL, fg=FG, selectcolor="#3a3a3a", activebackground=PANEL,
                       activeforeground=FG, font=("Sans", 11, "bold"), anchor="w").pack(fill="x")
        self.motor_msg = tk.Label(motors, bg=PANEL, fg="#e6b84d", font=("Sans", 9),
                                  wraplength=260, justify="left", anchor="w")
        self.motor_msg.pack(fill="x")

        threading.Thread(target=self._work, daemon=True).start()
        self.after(40, self._refresh)

    # ----- mode-specific controls -----
    def _face_controls(self):
        f = tk.Frame(self.controls, bg=PANEL)
        ttk.Button(f, text="➕ Enroll face in view…", command=self._enroll).pack(fill="x")
        ttk.Button(f, text="Forget all faces",
                   command=lambda: self.requests.put(("face", "forget_all", ()))).pack(
            fill="x", pady=(4, 0))
        return f

    def _follow_controls(self):
        f = tk.Frame(self.controls, bg=PANEL)
        tk.Label(f, text="Drag a box around an object on the video to follow it.", bg=PANEL,
                 fg=FG, font=("Sans", 10), wraplength=260, justify="left").pack(anchor="w")
        ttk.Button(f, text="Clear target",
                   command=lambda: self.requests.put(("follow", "clear", ()))).pack(
            fill="x", pady=(6, 0))
        return f

    def _gesture_controls(self, gestures):
        f = tk.Frame(self.controls, bg=PANEL)
        for _, desc in gestures.values():
            tk.Label(f, text=desc, bg=PANEL, fg=FG, font=("Sans", 10), anchor="w").pack(fill="x")
        return f

    def _drive_toggled(self, *_):
        self.drive_enabled = self.drive_var.get()
        if not self.drive_enabled:
            self.drive.stop()

    def _mode_changed(self):
        self.mode_key = self.mode_var.get()
        if self.mode_key == "off":
            self.drive.stop()
        for key, frame in self.mode_controls.items():
            if key == self.mode_key:
                frame.pack(fill="x")
            else:
                frame.pack_forget()

    def _enroll(self):
        name = simpledialog.askstring("Enroll face", "Name of the person facing the camera:",
                                      parent=self)
        if name and name.strip():
            self.requests.put(("face", "enroll", (name.strip(),)))

    # ----- selecting a target for follow mode -----
    def _to_frame(self, x, y):
        ox, oy, dw, dh, fw, fh = self.view
        return (min(max((x - ox) / dw, 0), 1) * fw, min(max((y - oy) / dh, 0), 1) * fh)

    def _drag_begin(self, e):
        if self.mode_key == "follow" and self.view:
            self.drag_start = (e.x, e.y)

    def _drag_move(self, e):
        if self.drag_start:
            self.canvas.delete("drag")
            self.canvas.create_rectangle(*self.drag_start, e.x, e.y, outline="#e6b84d", width=2,
                                         dash=(4, 2), tags="drag")

    def _drag_end(self, e):
        if not self.drag_start:
            return
        (x0, y0), (x1, y1) = self._to_frame(*self.drag_start), self._to_frame(e.x, e.y)
        self.drag_start = None
        self.canvas.delete("drag")
        box = (int(min(x0, x1)), int(min(y0, y1)), int(abs(x1 - x0)), int(abs(y1 - y0)))
        self.requests.put(("follow", "select", (box,)))

    # ----- background worker -----
    def _work(self):
        import cv2
        import numpy as np
        from vision.faces import FaceMode
        from vision.follow import FollowMode
        from vision.gestures import GestureMode
        try:
            modes = {"face": FaceMode(MODELS_DIR, FACES_DB), "follow": FollowMode(),
                     "gesture": GestureMode(MODELS_DIR)}
        except Exception as e:
            self.status_text = f"Could not load vision models: {e}"
            return
        self.status_text = ""
        last = -1
        while True:
            while not self.requests.empty():
                key, method, args = self.requests.get()
                getattr(modes[key], method)(*args)
            key = self.mode_key
            jpeg, frame_id = self.app.stream.latest()
            if jpeg is None or frame_id == last:
                time.sleep(0.02)
                continue
            last = frame_id
            frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue
            canvas = cv2.resize(frame, None, fx=SCALE, fy=SCALE)
            if key == "off":
                cmd = self.Command(reason="Autopilot off")
            else:
                try:
                    cmd = modes[key].process(frame, canvas, SCALE)
                except Exception as e:
                    cmd = self.Command(reason=f"Error: {e}")
                self.mode_message = modes[key].message
            manual = time.time() < getattr(self.app.drive_tab, "manual_until", 0)
            if self.drive_enabled and key != "off" and not manual:
                self.drive.send(cmd)
            with self.lock:
                self.output = (cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB), cmd, frame_id)

    # ----- UI refresh -----
    def _refresh(self):
        with self.lock:
            out = self.output
        if out and out[2] != self.shown_id:
            rgb, cmd, self.shown_id = out
            img = Image.fromarray(rgb)
            cw, ch = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
            scale = min(cw / img.width, ch / img.height)
            dw, dh = max(int(img.width * scale), 1), max(int(img.height * scale), 1)
            self.photo = ImageTk.PhotoImage(img.resize((dw, dh)))
            ox, oy = (cw - dw) // 2, (ch - dh) // 2
            self.canvas.delete("video")
            self.canvas.create_image(ox, oy, image=self.photo, anchor="nw", tags="video")
            self.canvas.tag_lower("video")
            self.view = (ox, oy, dw, dh, img.width / SCALE, img.height / SCALE)
            self.cmd_label.configure(text=COMMAND_TEXT[cmd.action],
                                     fg=COMMAND_COLOR[cmd.action] if self.mode_key != "off" else DIM)
            self.reason_label.configure(text=cmd.reason)
        elif not out:
            self.canvas.delete("waiting")
            self.canvas.create_text(self.canvas.winfo_width() // 2, self.canvas.winfo_height() // 2,
                                    text=self.status_text or "Waiting for camera…", fill="#aaa",
                                    font=("Sans", 14), tags="waiting")
        self.mode_msg.configure(text=self.mode_message if self.mode_key != "off" else
                                self.status_text)
        if not self.drive_enabled:
            motor = "Off: commands are shown but not sent."
        elif not self.drive.connected:
            motor = "Waiting for Bluetooth — connect in the Drive tab."
        else:
            motor = "ON: the bot follows these commands. Space/Esc = STOP."
        self.motor_msg.configure(text=motor)
        self.after(40, self._refresh)
