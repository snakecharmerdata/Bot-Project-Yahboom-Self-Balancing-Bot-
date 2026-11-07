"""Camera bridge: ROS2 camera topic -> HTTP.

Runs inside the ros:humble Docker container (see camera/start_bridge.sh).
Subscribes to the ESP32 camera's CompressedImage topic and serves:
  /snapshot.jpg  latest frame
  /stream        MJPEG live stream (viewable in a browser too)
  /status        JSON: frame count, fps, age of last frame
"""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

TOPIC = os.environ.get("CAMERA_TOPIC", "/espRos/esp32camera")
PORT = int(os.environ.get("BRIDGE_PORT", "8080"))


class FrameStore:
    def __init__(self):
        self.cond = threading.Condition()
        self.jpeg = None
        self.count = 0
        self.stamp = 0.0
        self.recent = []  # arrival times, for fps

    def put(self, data):
        now = time.time()
        with self.cond:
            self.jpeg = data
            self.count += 1
            self.stamp = now
            self.recent = [t for t in self.recent if now - t < 3.0] + [now]
            self.cond.notify_all()

    def fps(self):
        with self.cond:
            if len(self.recent) < 2:
                return 0.0
            return (len(self.recent) - 1) / (self.recent[-1] - self.recent[0])


store = FrameStore()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/snapshot.jpg":
            with store.cond:
                jpeg = store.jpeg
            if jpeg is None:
                self.send_error(503, "no frame yet")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpeg)))
            self.end_headers()
            self.wfile.write(jpeg)
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            last = -1
            try:
                while True:
                    with store.cond:
                        store.cond.wait_for(lambda: store.count != last, timeout=5)
                        if store.count == last:
                            continue
                        jpeg, last = store.jpeg, store.count
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode())
                    self.wfile.write(jpeg + b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == "/status":
            age = time.time() - store.stamp if store.stamp else None
            body = json.dumps({"frames": store.count, "fps": round(store.fps(), 1),
                               "last_frame_age_s": age}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)


def main():
    rclpy.init()
    node = rclpy.create_node("camera_bridge")
    node.create_subscription(CompressedImage, TOPIC,
                             lambda m: store.put(bytes(m.data)), qos_profile_sensor_data)
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    print(f"camera bridge: {TOPIC} -> http://0.0.0.0:{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
