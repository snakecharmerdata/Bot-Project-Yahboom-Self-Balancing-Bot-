"""Self Balancing Bot control app.

Dashboard for the Yahboom self-balancing bot:
  - Camera tab: live view from the ESP32-S3 WiFi camera, via the camera bridge
    (camera/bridge.py, started by camera/start_bridge.sh)
  - Autopilot tab: face recognition, object following and hand gestures
    (see autopilot.py and vision/)
  - Drive tab: manual Bluetooth control (see drive_tab.py and bot/drive.py)
  - LiDAR tab: live radar view from the T-mini Plus on the USB-TTL adapter
    (see lidar_tab.py and lidar/tmini.py)
  - Status panel: camera, bridge, micro-ROS agent and bot Bluetooth connection

Run:  .venv/bin/python main.py   (or use the desktop icon, see install_launcher.sh)
"""
import io
import json
import os
import subprocess
import threading
import time
import tkinter as tk
import urllib.request
from datetime import datetime
from tkinter import ttk

from PIL import Image, ImageTk

import settings
from autopilot import AutopilotTab
from bot.drive import BleDrive
from drive_tab import DriveTab
from lidar.guard import ObstacleGuard
from lidar.tmini import TMiniLidar
from lidar_tab import LidarTab

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BRIDGE_URL = "http://localhost:8080"
SNAPSHOT_DIR = os.path.join(APP_DIR, "camera_snapshots")

BG = "#1e1e1e"
PANEL = "#2a2a2a"
FG = "#dddddd"
DIM = "#888888"
OK = "#66cc66"
WARN = "#e6b84d"
BAD = "#e66666"


class CameraStream:
    """Reads the bridge's MJPEG stream in a background thread, reconnecting as needed."""

    def __init__(self, url):
        self.url = url
        self.lock = threading.Lock()
        self.jpeg = None
        self.frame_id = 0
        self.connected = False
        self.recent = []
        threading.Thread(target=self._run, daemon=True).start()

    def latest(self):
        with self.lock:
            return self.jpeg, self.frame_id

    def fps(self):
        with self.lock:
            now = time.time()
            recent = [t for t in self.recent if now - t < 3.0]
            if len(recent) < 2:
                return 0.0
            return (len(recent) - 1) / (recent[-1] - recent[0])

    def _run(self):
        while True:
            try:
                with urllib.request.urlopen(self.url + "/stream", timeout=5) as resp:
                    self.connected = True
                    self._read_frames(resp)
            except Exception:
                pass
            self.connected = False
            time.sleep(1)

    def _read_frames(self, resp):
        while True:
            line = resp.readline()
            if not line:
                return
            if not line.lower().startswith(b"content-length:"):
                continue
            length = int(line.split(b":")[1])
            resp.readline()  # blank line after headers
            data = resp.read(length)
            now = time.time()
            with self.lock:
                self.jpeg = data
                self.frame_id += 1
                self.recent = [t for t in self.recent if now - t < 3.0] + [now]


class SystemStatus:
    """Polls the services the app depends on, in a background thread."""

    def __init__(self):
        self.state = {}
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            self.state = self._check()
            time.sleep(3)

    @staticmethod
    def _container_running(name):
        try:
            out = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                                 capture_output=True, text=True, timeout=5)
            return out.stdout.strip() == "true"
        except Exception:
            return False

    def _check(self):
        bridge, camera_age = False, None
        try:
            with urllib.request.urlopen(BRIDGE_URL + "/status", timeout=2) as r:
                camera_age = json.load(r).get("last_frame_age_s")
                bridge = True
        except Exception:
            pass
        return {
            "agent": self._container_running("microros_agent"),
            "bridge": bridge,
            "camera": camera_age is not None and camera_age < 3,
        }


class StatusRow(tk.Frame):
    def __init__(self, parent, label):
        super().__init__(parent, bg=PANEL)
        self.dot = tk.Label(self, text="●", bg=PANEL, fg=DIM, font=("Sans", 12))
        self.dot.pack(side="left")
        tk.Label(self, text=label, bg=PANEL, fg=FG, font=("Sans", 11), anchor="w").pack(
            side="left", padx=(6, 0))
        self.detail = tk.Label(self, bg=PANEL, fg=DIM, font=("Sans", 9), anchor="e")
        self.detail.pack(side="right")

    def set(self, color, detail):
        self.dot.configure(fg=color)
        self.detail.configure(text=detail)


class CameraTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self.stream = app.stream
        self.shown_id = -1
        self.photo = None
        self.flash_until = 0.0

        self.video = tk.Label(self, bg="black", fg="#aaa", text="Connecting to camera…",
                              font=("Sans", 14))
        self.video.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        self.info = tk.Label(bar, bg=BG, fg=FG, anchor="w", font=("Sans", 11))
        self.info.pack(side="left", fill="x", expand=True)
        ttk.Button(bar, text="📁 Open snapshots", command=self.open_folder).pack(side="right")
        ttk.Button(bar, text="📷 Snapshot", command=self.snapshot).pack(side="right", padx=6)

        self.after(30, self.update_frame)

    def update_frame(self):
        jpeg, frame_id = self.stream.latest()
        if jpeg and frame_id != self.shown_id:
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

        if time.time() < self.flash_until:
            pass  # keep showing the snapshot message
        elif self.stream.connected:
            self.info.configure(text=f"● Live   {self.stream.fps():.1f} fps", fg=OK)
        else:
            self.info.configure(text="● No video — see Status panel", fg=BAD)
        self.after(30, self.update_frame)

    def snapshot(self):
        jpeg, _ = self.stream.latest()
        if not jpeg:
            return
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        path = os.path.join(SNAPSHOT_DIR, datetime.now().strftime("snap_%Y%m%d_%H%M%S.jpg"))
        with open(path, "wb") as f:
            f.write(jpeg)
        self.info.configure(text=f"Saved {os.path.basename(path)}", fg="#66ccff")
        self.flash_until = time.time() + 2

    def open_folder(self):
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        subprocess.Popen(["xdg-open", SNAPSHOT_DIR])


class ComingSoonTab(tk.Frame):
    def __init__(self, parent, title, text):
        super().__init__(parent, bg=BG)
        box = tk.Frame(self, bg=BG)
        box.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(box, text=title, bg=BG, fg=FG, font=("Sans", 18, "bold")).pack()
        tk.Label(box, text=text, bg=BG, fg=DIM, font=("Sans", 11), justify="center").pack(pady=8)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Self Balancing Bot")
        self.geometry("1050x680")
        self.minsize(700, 450)
        self.configure(bg=BG)
        icon = os.path.join(APP_DIR, "assets", "icon.png")
        if os.path.exists(icon):
            self.iconphoto(True, tk.PhotoImage(file=icon))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=FG, padding=(16, 6),
                        font=("Sans", 11))
        style.map("TNotebook.Tab", background=[("selected", "#3a3a3a")])
        style.configure("TButton", padding=(10, 4))

        self.status = SystemStatus()
        self.settings = settings.load()
        self.stream = CameraStream(BRIDGE_URL)
        self.lidar = TMiniLidar(self.settings["lidar_port"])
        self.lidar.start()
        self.guard = ObstacleGuard(self.lidar, self.settings)
        self.drive = BleDrive(self.settings["bot_ble_address"])
        self.drive.guard = self.guard
        self._build_sidebar()

        self.tabs = tabs = ttk.Notebook(self)
        tabs.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        tabs.add(CameraTab(tabs, self), text="📷  Camera")
        self.drive_tab = DriveTab(tabs, self)
        self.autopilot = AutopilotTab(tabs, self)
        tabs.add(self.autopilot, text="🤖  Autopilot")
        tabs.add(self.drive_tab, text="🕹  Drive")
        self.lidar_tab = LidarTab(tabs, self)
        tabs.add(self.lidar_tab, text="📡  LiDAR")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.after(500, self.refresh_status)

    def _build_sidebar(self):
        side = tk.Frame(self, bg=PANEL, width=240)
        side.pack(side="left", fill="y", padx=8, pady=8)
        side.pack_propagate(False)
        tk.Label(side, text="Self Balancing Bot", bg=PANEL, fg=FG,
                 font=("Sans", 14, "bold")).pack(anchor="w", padx=12, pady=(14, 2))
        tk.Label(side, text="Yahboom · STM32F103", bg=PANEL, fg=DIM,
                 font=("Sans", 9)).pack(anchor="w", padx=12, pady=(0, 14))

        tk.Label(side, text="STATUS", bg=PANEL, fg=DIM, font=("Sans", 9, "bold")).pack(
            anchor="w", padx=12, pady=(0, 4))
        self.rows = {}
        for key, label in (("camera", "Camera"), ("bridge", "Camera bridge"),
                           ("agent", "micro-ROS agent"), ("bot", "Bot (Bluetooth)")):
            row = StatusRow(side, label)
            row.pack(fill="x", padx=12, pady=3)
            self.rows[key] = row

        ttk.Button(side, text="↻ Restart camera services",
                   command=self.restart_services).pack(fill="x", padx=12, pady=(16, 4))
        self.msg = tk.Label(side, bg=PANEL, fg=DIM, font=("Sans", 9), wraplength=210,
                            justify="left")
        self.msg.pack(anchor="w", padx=12)

    def refresh_status(self):
        s = self.status.state
        if s:
            self.rows["camera"].set(OK if s["camera"] else BAD,
                                    "streaming" if s["camera"] else "no frames")
            self.rows["bridge"].set(OK if s["bridge"] else BAD,
                                    "running" if s["bridge"] else "stopped")
            self.rows["agent"].set(OK if s["agent"] else BAD,
                                   "running" if s["agent"] else "stopped")
        if self.drive.connected:
            self.rows["bot"].set(OK, "connected")
        elif self.drive.enabled:
            self.rows["bot"].set(WARN, "connecting…")
        else:
            self.rows["bot"].set(DIM, "not connected")
        self.after(1000, self.refresh_status)

    def save_settings(self):
        settings.save(self.settings)

    def disable_autopilot_driving(self):
        if hasattr(self.autopilot, "drive_var"):
            self.autopilot.drive_var.set(False)

    def on_close(self):
        self.drive.stop()
        self.disable_autopilot_driving()
        self.drive.disconnect()
        self.lidar.stop()  # its worker sends the LiDAR's stop-scan command
        self.after(400, self.destroy)  # give the workers time to send their final STOPs

    def restart_services(self):
        self.msg.configure(text="Restarting…")

        def work():
            subprocess.run(["docker", "restart", "microros_agent"], capture_output=True)
            res = subprocess.run([os.path.join(APP_DIR, "camera", "start_bridge.sh")],
                                 capture_output=True, text=True)
            text = "Restarted. The camera may take ~10 s to reconnect." if res.returncode == 0 \
                else f"Restart failed: {res.stderr.strip()[:120]}"
            self.after(0, lambda: self.msg.configure(text=text))

        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
