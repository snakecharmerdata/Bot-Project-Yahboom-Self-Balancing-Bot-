"""Drive output for the bot, over Bluetooth LE.

The bot's BT module is a BLE serial bridge (service FFE0, characteristic FFE1)
in front of the Yahboom balance-car protocol: `$A,B,0,0,0,0,0,0,0,0#`, where
A = 0 stop / 1 forward / 2 backward / 3 left / 4 right and B = 1 spin left /
2 spin right.

The bot only moves while it keeps receiving commands, so BleDrive resends the
current command every SEND_INTERVAL_S. If no one has renewed the command for
COMMAND_TIMEOUT_S (released key, frozen UI, vision stopped), it sends STOP.

Note: the Pi's built-in Bluetooth only holds this connection reliably while
the Pi's WiFi radio is off (shared radio chip) — run the Pi on Ethernet.
"""
import asyncio
import threading
import time

SERIAL_SERVICE = "0000ffe0-0000-1000-8000-00805f9b34fb"
SERIAL_CHAR = "0000ffe1-0000-1000-8000-00805f9b34fb"
SEND_INTERVAL_S = 0.1
COMMAND_TIMEOUT_S = 0.5

PACKETS = {
    "stop": b"$0,0,0,0,0,0,0,0,0,0#",
    "forward": b"$1,0,0,0,0,0,0,0,0,0#",
    "backward": b"$2,0,0,0,0,0,0,0,0,0#",
    "left": b"$3,0,0,0,0,0,0,0,0,0#",
    "right": b"$4,0,0,0,0,0,0,0,0,0#",
    "spin_left": b"$0,1,0,0,0,0,0,0,0,0#",
    "spin_right": b"$0,2,0,0,0,0,0,0,0,0#",
}


def _looks_like_bot(device, adv):
    """Yahboom's module advertises the FFE0 serial service; its name ("YahBoom_BL")
    often only shows up once connected."""
    name = (adv.local_name or device.name or "").lower()
    return "yahboom" in name or SERIAL_SERVICE in [u.lower() for u in adv.service_uuids]


class BleDrive:
    def __init__(self, address=None):
        # None = use the first nearby device that looks like the bot's module.
        # Set "bot_ble_address" in settings.json if other BLE serial devices are around.
        self.address = address
        self.enabled = False      # user wants to be connected
        self.connected = False
        self.status = "Not connected"
        self.last_sent = "stop"
        self.guard = None         # optional ObstacleGuard, applied to every command sent
        self._action = "stop"
        self._action_time = 0.0
        threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True).start()

    # ----- called from the UI / vision threads -----
    def connect(self):
        self.enabled = True

    def disconnect(self):
        self.enabled = False

    def send(self, cmd):
        """Request a movement. Accepts an action name or a vision Command.
        Must be renewed at least every COMMAND_TIMEOUT_S to keep moving."""
        action = cmd if isinstance(cmd, str) else cmd.action
        if action not in PACKETS:
            action = "stop"
        self._action, self._action_time = action, time.time()

    def stop(self):
        self.send("stop")

    # ----- Bluetooth worker -----
    async def _write(self, client, packet):
        for i in range(0, len(packet), 20):  # BLE packets carry at most 20 bytes
            await client.write_gatt_char(SERIAL_CHAR, packet[i:i + 20], response=False)

    async def _main(self):
        from bleak import BleakClient, BleakScanner

        while True:
            if not self.enabled:
                self.status = "Not connected"
                await asyncio.sleep(0.2)
                continue
            try:
                self.status = "Searching for the bot…"
                if self.address:
                    dev = await BleakScanner.find_device_by_address(self.address, timeout=8)
                else:
                    dev = await BleakScanner.find_device_by_filter(_looks_like_bot, timeout=8)
                if not dev:
                    self.status = "Bot not found — is it switched on?"
                    continue
                self.status = "Connecting…"
                dropped = asyncio.Event()
                async with BleakClient(dev, timeout=20,
                                       disconnected_callback=lambda _: dropped.set()) as client:
                    self.connected = True
                    self.status = "Connected"
                    while self.enabled and not dropped.is_set():
                        fresh = time.time() - self._action_time < COMMAND_TIMEOUT_S
                        action = self._action if fresh else "stop"
                        if self.guard:
                            action = self.guard.filter(action)
                        await self._write(client, PACKETS[action])
                        self.last_sent = action
                        await asyncio.sleep(SEND_INTERVAL_S)
                    if not dropped.is_set():
                        for _ in range(3):
                            await self._write(client, PACKETS["stop"])
                            await asyncio.sleep(0.05)
                if self.enabled:
                    self.status = "Connection lost — reconnecting…"
            except Exception as e:
                self.status = f"Connection failed ({type(e).__name__}) — retrying…"
            finally:
                self.connected = False
                self.last_sent = "stop"
            await asyncio.sleep(1)
