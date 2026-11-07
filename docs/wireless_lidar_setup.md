# Wireless LiDAR setup (ESP32 WiFi bridge)

Goal: see the LiDAR map in the Self Balancing Bot app **with no cables between
the bot and the Pi**. A small ESP32 board rides on the bot, reads the LiDAR,
and sends its data to the Pi over WiFi.

---

## How everything connects

```
┌────────────── THE BOT (no cables leaving it) ──────────────┐
│                                                            │
│  Battery → Yahboom board ──5V/GND──► ESP32 ──► LiDAR        │
│               │      │                  │                  │
│        Bluetooth   Camera (UART2)       │                  │
│        module                           │                  │
└───────────┼──────────────┼──────────────┼──────────────────┘
       Bluetooth         WiFi           WiFi
       (driving)       (video)        (LiDAR)
            ▼              ▼              ▼
      ┌──────────────── Raspberry Pi ─────────────────┐
      │  Drive · Camera · LiDAR map · Autopilot        │
      └────────────────────────────────────────────────┘
```

| Signal | Travels by | Cable to the Pi? |
|---|---|---|
| Driving commands | Bluetooth (bot's module) | No |
| Camera video | WiFi (camera's own ESP32-S3) | No |
| LiDAR map | WiFi (new ESP32) | No |
| Power | Bot's battery | No |

**Why a new ESP32:** the Yahboom board has no WiFi and never sends LiDAR data
over Bluetooth. The camera has WiFi, but its software only sends images.

---

## Parts

- [x] YDLIDAR T-mini Plus (Yahboom "T-MINI-Plus"), already have
- [ ] ESP32 development board with pins pre-soldered, on order
      (model: ____________; needed for the exact RX/TX pin numbers)
- [x] Adapter cable: white plug on one end, loose wire ends on the other
- [x] Jumper wires
- [x] USB cable for the ESP32 (for programming only)
- [x] USB-TTL adapter, kept as a spare for testing

---

## Wiring (final, on the bot)

> Switch the bot **off** before changing any wiring.
> Wire by **function** (5V, GND, RX, TX), not by colour. This kit's camera cable
> used non-standard colours.

### Power: bot's UART3 port → ESP32

Plug the adapter cable's white plug into the bot's **UART3** port (where the
LiDAR used to plug in). Use **only** the 5V and GND wires.

| Bot UART3 pin | → ESP32 pin |
|---|---|
| 5V | 5V (sometimes labelled VIN) |
| GND | GND |
| RX3 | **not connected**, tape the wire end |
| TX3 | **not connected**, tape the wire end |

### LiDAR → ESP32

| LiDAR wire | Function | → ESP32 pin |
|---|---|---|
| Red | 5V power | 5V / VIN |
| Black | Ground | GND |
| Green | LiDAR TX (data out) | RX pin: ______ (filled in once the board model is known) |
| Yellow | LiDAR RX (commands in) | TX pin: ______ (filled in once the board model is known) |

Both the ESP32 and the LiDAR use **3.3 V signals**, so they connect directly.

### Unchanged

- **Camera** stays on **UART2** (power only; it sends video over WiFi).
- **Bluetooth module** stays in its socket (driving).

---

## Setup steps

### Step 1: Program the ESP32 (on the desk)
1. Plug the ESP32 into the Pi with its **USB cable only**. Nothing else connected.
2. Tell Claude the board model. Claude flashes the WiFi serial bridge firmware with:
   - WiFi network: your **2.4 GHz** network (ESP32 boards only support 2.4 GHz)
   - LiDAR serial: 230400 baud
   - Bridge port: 8888 (planned)
3. Note the ESP32's IP address: `_______________`

### Step 2: Test on the desk (still powered by USB)
1. Wire the LiDAR to the ESP32 as in the table above.
2. Unplug the USB-TTL adapter from the Pi.
3. In the app's settings, point the LiDAR at the ESP32 (Claude does this):
   `settings.json` → `"lidar_port": "socket://<ESP32 IP>:8888"`
4. Open the **LiDAR** tab and check the radar view appears.

### Step 3: Move it onto the bot
1. Switch the bot **off**.
2. Mount the ESP32 and LiDAR on the bot.
3. Connect power from the bot's **UART3** port (5V and GND only; tape RX3 and TX3).
4. Unplug the ESP32's USB cable.
5. Switch the bot **on**. The ESP32 joins WiFi and the LiDAR starts spinning.
6. Check in the app: LiDAR map, camera, and driving all working with no cables.

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
- **Power:** the bot's 5V now feeds the camera, the ESP32 and the LiDAR. If
  anything restarts randomly, check power first.
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
| Map works on the desk but not on the bot | Bot power: 5V/GND from UART3 the right way round |
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
