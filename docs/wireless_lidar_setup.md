# Wireless LiDAR setup (ESP32 WiFi bridge)

Goal: see the LiDAR map in the Self Balancing Bot app **with no cables between
the bot and the Pi**. A small ESP32 board rides on the bot, reads the LiDAR,
and sends its data to the Pi over WiFi.

---

## How everything connects

```
ESP32 DevKit V1 ──WiFi──► Raspberry Pi app
      ▲
      └── LiDAR (UART)
      └── Regulated 5V supply
```

| Signal | Travels by | Cable to the Pi? |
|---|---|---|
| Driving commands | Bluetooth (bot's module) | No |
| Camera video | WiFi (camera's own ESP32-S3) | No |
| LiDAR map | WiFi (new ESP32) | No |
| Power (bench test) | Separate regulated 5V supply | No |

**Why a new ESP32:** the Yahboom board has no WiFi and never sends LiDAR data
over Bluetooth. The camera has WiFi, but its software only sends images.

---

## Parts

- [x] YDLIDAR T-mini Plus (Yahboom "T-MINI-Plus"), already have
- [x] ESP32 DevKit V1
- [x] Adapter cable: white plug on one end, loose wire ends on the other
- [x] Jumper wires
- [x] USB cable for the ESP32 (for programming only)
- [x] USB-TTL adapter, kept as a spare for testing

---

## Wiring (wireless LiDAR test)

Keep the bot disconnected while testing the wireless bridge. The project
README identifies UART3 with the Bluetooth module, so do not use UART3 for
ESP32 power or connect the LiDAR to UART3 at the same time as the ESP32.
Use a single, regulated 5V supply for the ESP32 and LiDAR, with enough current
for both. The LiDAR and ESP32 must share GND. Do not power the LiDAR from the
Pi's USB port.

### LiDAR → ESP32

| LiDAR wire | Function | → ESP32 pin |
|---|---|---|
| Red | 5V power | Regulated 5V |
| Black | Ground | GND |
| Green | LiDAR TX (data out) | GPIO16 / RX2 |
| Yellow | LiDAR RX (commands in) | GPIO17 / TX2 |

The LiDAR uses 3.3V serial logic and 5V power. Do not connect its red power
wire to the ESP32's 3.3V pin.

---

## Setup steps

### Step 1: Program the ESP32 (on the desk)
1. In Arduino IDE, open `esp32_lidar_bridge/esp32_lidar_bridge.ino`.
2. Select **ESP32 Dev Module** and the ESP32's USB serial port.
3. In the sketch, enter the name and password of your **2.4 GHz** WiFi network
   locally. Do not share or commit those credentials.
4. Upload the sketch. Open Serial Monitor at **115200 baud** and note the IP
   address printed after `Wi-Fi connected`. The bridge listens on TCP port
   **8888**.

### Step 2: Test on the desk
1. With power disconnected, wire the LiDAR to the ESP32 as in the table above.
2. Unplug the USB-TTL adapter from the Pi.
3. Power the ESP32 and LiDAR from a regulated 5V source that can supply both.
   Do not connect the LiDAR's 5V to the Pi's USB power.
4. Set `settings.json` to use the bridge:
   `"lidar_port": "socket://<ESP32 IP>:8888"`
5. Open the **LiDAR** tab and check the radar view appears.

### Step 3: Mounting on the bot

Do not connect the ESP32 to UART3 based on this guide. Verify the bot's actual
UART3 pinout and power capability first; the README identifies UART3 with the
Bluetooth module. Keep the ESP32 and LiDAR on their verified 5V supply, and
leave the LiDAR's UART3 connection disconnected during wireless operation.

### Step 4: Line up "front"
1. In the **LiDAR** tab, click **Rotate view 90°** until the side the bot faces
   is at the top. The setting is saved.
2. The **obstacle stop** uses the same "front", so it now protects the real bot.

---

## Things to know

- **The bot's built-in LiDAR modes** (Lidar follow, patrol, and so on) won't work
  while the LiDAR is on the ESP32. To use them, plug the LiDAR back into UART3.
- **The Pi must stay on 5 GHz WiFi** (or Ethernet). On 2.4 GHz the Pi's
  Bluetooth becomes unreliable. The ESP32 and camera use 2.4 GHz; that's fine,
  since only the Pi's own WiFi matters for Bluetooth.
- **Power:** choose a verified 5V source rated for the ESP32 and LiDAR together.
  Do not assume the bot's UART3 or an ESP32 VIN pin is suitable without checking
  the board pinout and current rating.
- **Obstacle stop** (Drive tab): stops forward or turning commands when something
  is within 0.35 m in front, and backward commands when something is within 0.35 m
  behind. Spinning on the spot is always allowed.
- **Cables you'll still use sometimes:** charging the battery, and reprogramming
  the ESP32 (USB).

---

## Troubleshooting

| Problem | Check |
|---|---|
| LiDAR tab says "Not connected" | Is the ESP32 powered? Is it on WiFi? Is `lidar_port` set to the ESP32's IP? |
| LiDAR doesn't spin | 5V/GND on the ESP32, and red/black on 5V/GND |
| Spins but no map | Green ↔ yellow swapped (green must go to the ESP32's RX pin) |
| Map works on the desk but not on the bot | Check the verified 5V supply and WiFi signal |
| Obstacle stop says "not protecting" | No fresh LiDAR data; see the rows above |
| Driving stops working | Pi must be on 5 GHz WiFi; Bluetooth module still in its socket |

---

## Fallback: wired LiDAR (works today)

```
LiDAR → USB-TTL adapter → Pi USB
```

| LiDAR wire | → USB-TTL pin |
|---|---|
| Red | 5V |
| Black | GND |
| Green | RXD |
| Yellow | TXD |

The adapter's jumper goes on **VCC–3V3**. The app finds the adapter by itself.
