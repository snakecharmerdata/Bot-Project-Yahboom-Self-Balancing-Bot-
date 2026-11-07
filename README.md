# Self Balancing Bot

A desktop app for the **Yahboom STM32 self-balancing robot**, running on a
**Raspberry Pi 5**. It drives the bot over Bluetooth and shows a live camera
view and a LiDAR radar map. It also adds camera-based autopilot modes: face
recognition, object following and hand gestures.

The bot's factory firmware is left untouched. The Pi does all the thinking and
sends the same Bluetooth commands as Yahboom's phone app.

| Tab | What it does |
|---|---|
| 📷 Camera | Live view from the WiFi camera, with snapshots |
| 🤖 Autopilot | Face recognition, follow an object, hand gestures; can steer the bot |
| 🕹 Drive | Live camera plus hold-to-drive buttons and keys, with obstacle stop |
| 📡 LiDAR | Live 360° radar view, nearest object and obstacle-stop zones |

> Not affiliated with Yahboom. Use at your own risk: it's a robot with motors.

---

## Hardware

- Yahboom STM32 self-balancing robot (STM32F103RC board, Bluetooth module in UART3)
- Raspberry Pi 5 running Raspberry Pi OS / Debian 13 (64-bit)
- Yahboom **ESP32-S3 ROS WiFi camera** (sends images over WiFi with micro-ROS)
- Yahboom **T-MINI-Plus** LiDAR (= YDLIDAR T-mini Plus)
- A CH340 **USB-TTL adapter** (for camera setup and the wired LiDAR)

## How it fits together

```
 Bot (STM32) ◄──── Bluetooth LE ────┐
 Camera (ESP32-S3) ── WiFi ──► micro-ROS agent (Docker) ─► camera bridge (Docker) ─┐
 LiDAR ── USB-TTL adapter ─────────────────────────────────────────────────────────┤
                                                                                   ▼
                                                            Raspberry Pi: main.py (app)
```

---

## Setup

### 1. System packages

```bash
sudo apt update
sudo apt install -y git python3-venv python3-opencv python3-pil.imagetk python3-serial
sudo usermod -aG dialout $USER           # serial ports (USB-TTL adapter)

# Docker, for the ROS 2 camera services
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Log out and back in (or reboot) so the new groups take effect.

### 2. Get the code and the Python environment

```bash
git clone <this repository's URL> "Self Balancing Bot"
cd "Self Balancing Bot"
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
tools/download_models.sh                  # face and gesture models (~46 MB)
```

### 3. Network: the important one

The Pi 5's Bluetooth and WiFi share one radio chip. **On 2.4 GHz WiFi the
Bluetooth link to the bot drops within seconds.** Put the Pi on **5 GHz WiFi
or Ethernet**. The camera (ESP32) still uses your 2.4 GHz network; that's fine,
as long as both are on the same router.

Give the Pi a fixed IP address (a DHCP reservation on your router is best),
because the camera is told which IP to send its images to.

### 4. Camera

1. **Wire the camera to the USB-TTL adapter by function, not by colour.** The
   cable in some kits uses non-standard colours. Check the labels on the bot's
   camera port to see which wire is 5V, GND, TX and RX.
   Adapter 5V → camera 5V, GND → GND, adapter TXD → camera RX, RXD → camera TX.
   Put the adapter's jumper on **VCC–3V3** (the camera uses 3.3 V logic).
2. Send it your WiFi details and the Pi's IP (the password prompt is hidden and nothing is saved):
   ```bash
   python3 tools/camera_wifi_setup.py /dev/ttyUSB0
   ```
3. Start the micro-ROS agent and the camera bridge. Both restart automatically on boot:
   ```bash
   docker run -d --name microros_agent --restart unless-stopped --net=host \
     microros/micro-ros-agent:humble udp4 --port 9999
   camera/start_bridge.sh
   ```
4. Plug the camera back into the bot for power. Check http://localhost:8080/stream in a browser.

The camera publishes `/espRos/esp32camera` (`sensor_msgs/CompressedImage`) on
ROS domain 20.

### 5. Bot (Bluetooth)

- On the bot's display, choose **1. Standard Mode**, stand it up and press its
  start button ("put down, key start"). It only accepts drive commands while balancing.
- Make sure your phone or tablet is **not** connected to the bot (one connection at a time).
- The app finds the bot's module automatically. If other BLE serial devices are
  nearby, set the address in `settings.json`:
  ```json
  { "bot_ble_address": "XX:XX:XX:XX:XX:XX" }
  ```
  To find the address: `bluetoothctl`, then `scan on`; look for "YahBoom_BL" or
  a device offering service `FFE0`.

### 6. LiDAR (wired for now)

| LiDAR wire | → USB-TTL adapter |
|---|---|
| Red (5V) | 5V |
| Black (GND) | GND |
| Green (LiDAR TX) | RXD |
| Yellow (LiDAR RX) | TXD |

The jumper goes on **VCC–3V3**. The app finds the adapter by its USB ID. It never
opens the bot's own USB "burn" port, because opening that resets the bot.
A wireless version (ESP32 WiFi bridge) is in progress; see
[docs/wireless_lidar_setup.md](docs/wireless_lidar_setup.md).

### 7. Run the app

```bash
.venv/bin/python main.py
./install_launcher.sh            # optional: desktop icon and menu entry
```

---

## Safety

- The bot only moves while it keeps receiving commands. The app resends the
  current command 10 times a second, and **stops** if nothing renewed it for 0.5 s
  (key released, link lost, app frozen).
- **Space / Esc** = stop, and switches off autopilot driving.
- **Obstacle stop** (Drive tab) blocks forward and turning commands when the LiDAR
  sees something within 0.35 m ahead (backward: behind). It only protects the bot
  once the LiDAR is mounted on it.
- Autopilot driving is **off** by default ("Let autopilot drive the bot").
- Don't hold the bot in the air while it's balancing: the wheels run away.

---

## Developing in VS Code

### Set up the editor

1. Install VS Code on the Pi: `sudo apt install code`.
   Or work from a PC with the **Remote - SSH** extension, connected to the Pi.
2. Open the project folder: **File → Open Folder… → Self Balancing Bot**.
3. Install the **Python** extension (Microsoft). It includes Pylance.
4. Select the interpreter: **Ctrl+Shift+P → "Python: Select Interpreter"** →
   `./.venv/bin/python`. This makes imports like `mediapipe` and `bleak` resolve.
5. Run or debug `main.py` with **F5** (choose "Python File").

### Add an AI coding assistant (optional)

Any of these work with this project; pick one:

| Option | What it is | Notes |
|---|---|---|
| **GitHub Copilot** | Inline completions and chat | Extension "GitHub Copilot"; needs a GitHub account and subscription (free tier available) |
| **Claude Code** | AI agent that can read, edit and run the project | Extension "Claude Code" or the `claude` CLI; needs an Anthropic account |
| **Continue** + **Ollama** | Open-source completions with a local model | Run Ollama on a PC with a decent GPU; the Pi 5 is too slow for comfortable local models |

Tips for good suggestions:
- Keep `.venv` selected as the interpreter so the assistant sees the real libraries.
- Point the assistant at this README and `docs/` for hardware facts (protocol,
  wiring, network gotchas). It can't infer those from the code.

---

## Project layout

```
main.py              App window: tabs, status panel, settings
drive_tab.py         Manual driving + live camera
autopilot.py         Autopilot tab (runs a vision mode, optionally drives)
lidar_tab.py         LiDAR radar view
settings.py          settings.json load/save (device-specific, not in git)
bot/drive.py         Bluetooth LE drive link (Yahboom protocol, 10 Hz resend, dead-man stop)
lidar/tmini.py       YDLIDAR T-mini Plus reader (USB-TTL or socket:// URL)
lidar/guard.py       Obstacle stop
vision/              Face recognition, object follow, hand gestures
camera/              ROS 2 camera → HTTP/MJPEG bridge (runs in Docker)
tools/               Camera WiFi setup, model download, Bluetooth drive test
docs/                Extra guides
```

### Bot command protocol (Yahboom balance car)

Text frames `$A,B,C,D,E,F,G,H,I,J#` over the BLE serial characteristic `FFE1`
(split writes into ≤ 20-byte chunks):

| Field | Values |
|---|---|
| A | 0 stop, 1 forward, 2 backward, 3 left, 4 right |
| B | 1 spin left, 2 spin right |
| C | 1 query PID, 2 restore factory PID |
| D | 1 auto-report on, 2 off |

With the factory firmware, the bot doesn't send any replies over Bluetooth.

---

## Troubleshooting

| Problem | Check |
|---|---|
| Bluetooth connects then drops | Is the Pi on 2.4 GHz WiFi? Move it to 5 GHz or Ethernet |
| Bot visible but ignores commands | Standard Mode, start button pressed, balancing; tablet disconnected |
| No camera video | Agent and bridge running (`docker ps`); camera told the right Pi IP; power-cycle the camera |
| LiDAR "not connected" | USB-TTL adapter plugged in; red/black on 5V/GND; green → RXD |
| Autopilot tab says "needs the project's Python environment" | Start with `.venv/bin/python main.py` |

## Credits

- Bot protocol: Yahboom's balance-car Bluetooth protocol document
- [MediaPipe](https://developers.google.com/mediapipe) gesture recognizer
- [OpenCV Zoo](https://github.com/opencv/opencv_zoo) YuNet face detector and SFace recognizer
- [bleak](https://github.com/hbldh/bleak) Bluetooth LE library

Check each model's own license page before redistributing the model files.
