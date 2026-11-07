"""Short, bounded Bluetooth drive test for the bot. Always ends with STOP.

Usage: .venv/bin/python tools/ble_drive_test.py [pulse|once] <bot BLE address>
  pulse  send FORWARD continuously for 1 s, then STOP
  once   send FORWARD a single time, wait 3 s (does the bot stop by itself?), then STOP
"""
import asyncio
import sys
import time

from bleak import BleakClient, BleakScanner

ADDR = sys.argv[2] if len(sys.argv) > 2 else None
CH = "0000ffe1-0000-1000-8000-00805f9b34fb"
FWD = b"$1,0,0,0,0,0,0,0,0,0#"
STOP = b"$0,0,0,0,0,0,0,0,0,0#"


async def send(c, cmd):
    for i in range(0, len(cmd), 20):  # BLE packets carry at most 20 bytes
        await c.write_gatt_char(CH, cmd[i:i + 20], response=False)
        await asyncio.sleep(0.02)


async def run(mode):
    dev = await BleakScanner.find_device_by_address(ADDR, timeout=8)
    if not dev:
        print("bot not found")
        return
    async with BleakClient(dev, timeout=25) as c:
        print("connected", time.strftime("%H:%M:%S"), flush=True)
        await send(c, STOP)
        await asyncio.sleep(1.5)
        try:
            print("FORWARD", time.strftime("%H:%M:%S"), flush=True)
            if mode == "once":
                await send(c, FWD)
                await asyncio.sleep(3)
            else:
                t = time.time()
                while time.time() - t < 1.0:
                    await send(c, FWD)
                    await asyncio.sleep(0.05)
        finally:
            for _ in range(8):
                await send(c, STOP)
                await asyncio.sleep(0.05)
            print("STOP", time.strftime("%H:%M:%S"), flush=True)


async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "pulse"
    if not ADDR:
        print(__doc__)
        return
    try:
        await asyncio.wait_for(run(mode), timeout=40)
    except Exception as e:
        print("gave up:", type(e).__name__, e)


asyncio.run(main())
