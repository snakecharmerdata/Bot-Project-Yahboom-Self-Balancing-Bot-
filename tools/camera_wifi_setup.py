"""One-time setup of the Yahboom ESP32-S3 ROS WiFi camera over its USB-TTL adapter.

Sends the WiFi name, password and the ROS2 host (this Pi's) IP address.
The password is typed in at a hidden prompt and is never saved anywhere.

Usage: python3 tools/camera_wifi_setup.py [/dev/ttyUSB0]

Camera serial: 115200 baud, commands WITHOUT a trailing newline.
"""
import getpass
import sys
import time

import serial


def send(s, cmd):
    s.reset_input_buffer()
    s.write(cmd.encode())
    s.flush()
    time.sleep(2)
    return s.read(s.in_waiting or 1).decode("utf-8", "replace").strip()


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    ssid = input("WiFi network name (2.4 GHz): ").strip()
    password = getpass.getpass("WiFi password: ")
    host_ip = input("IP address of the Pi running the micro-ROS agent: ").strip()
    with serial.Serial(port, 115200, timeout=0.5) as s:
        s.dtr = s.rts = False
        print("sta_ssid ->", send(s, f"sta_ssid:{ssid}")[:60])
        print("sta_pd   ->", send(s, f"sta_pd:{password}")[:60])
        print("ros2_ip  ->", send(s, f"ros2_ip:{host_ip}")[:60], "(the camera restarts)")


if __name__ == "__main__":
    main()
