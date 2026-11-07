"""Reader for the YDLIDAR T-mini Plus (sold by Yahboom as "T-MINI-Plus").

Serial: 230400 baud, 3.3 V logic, 5 V power. Commands are two bytes (0xA5, cmd).
Scan data arrives in packets:

    AA 55 | CT | LSN | FSA(2) | LSA(2) | CS(2) | LSN samples
    CT bit 0 = 1 marks the first packet of a new rotation.
    FSA/LSA: start/end angle, (value >> 1) / 64 degrees.
    Each sample is 3 bytes: intensity, then distance in mm as
    (b2 << 6) | (b1 >> 2), with b1's low 2 bits extending intensity.
    CS = XOR of the 16-bit words of the header and the samples.

Usage:
    lidar = TMiniLidar(); lidar.start()   # finds the USB-TTL adapter by itself
    scan = lidar.latest_scan()   # list of (angle_deg, distance_mm, intensity)
"""
import struct
import threading
import time

import serial

CMD_STOP = b"\xa5\x65"
CMD_SCAN = b"\xa5\x60"
CMD_INFO = b"\xa5\x90"
BAUD = 230400
# The USB-TTL adapter (CH340, 1a86:7523). The bot's own burn port is 1a86:7522 —
# never open that one: it resets the bot.
ADAPTER_VID_PID = (0x1A86, 0x7523)


def find_port():
    from serial.tools import list_ports
    for p in list_ports.comports():
        if (p.vid, p.pid) == ADAPTER_VID_PID:
            return p.device
    return None


def parse_packets(buf):
    """Yield (is_new_rotation, [(angle, dist_mm, intensity), ...]) from buf.
    Returns the unparsed remainder via the generator's final value."""
    i = 0
    while True:
        j = buf.find(b"\xaa\x55", i)
        if j < 0 or len(buf) - j < 10:
            return buf[j:] if j >= 0 else b""
        ct, lsn = buf[j + 2], buf[j + 3]
        end = j + 10 + 3 * lsn
        if lsn == 0 or end > len(buf):
            if end > len(buf) and lsn:
                return buf[j:]
            i = j + 2
            continue
        fsa, lsa, cs = struct.unpack_from("<HHH", buf, j + 4)
        samples = buf[j + 10:end]
        check = 0x55AA ^ fsa ^ lsa ^ (ct | (lsn << 8))
        points = []
        for k in range(lsn):
            b0, b1, b2 = samples[3 * k:3 * k + 3]
            check ^= b0 ^ (b1 | (b2 << 8))
            points.append(((b2 << 6) | (b1 >> 2), b0 | ((b1 & 0x03) << 8)))
        i = end
        if check != cs:
            continue  # corrupt packet
        start, stop = (fsa >> 1) / 64.0, (lsa >> 1) / 64.0
        span = (stop - start) % 360.0
        step = span / (lsn - 1) if lsn > 1 else 0.0
        yield bool(ct & 0x01), [((start + step * k) % 360.0, d, inten)
                                for k, (d, inten) in enumerate(points)]


class TMiniLidar:
    def __init__(self, port=None):
        self.port = port  # None = find the USB-TTL adapter on each (re)connect
        self.lock = threading.Lock()
        self._scan = []
        self.scan_time = 0.0  # when the latest full rotation finished
        self.scans = 0
        self.connected = False
        self.error = ""
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False

    def latest_scan(self):
        with self.lock:
            return list(self._scan)

    def scan_age(self):
        """Seconds since the last full rotation (inf if none yet)."""
        return time.time() - self.scan_time if self.scan_time else float("inf")

    def _run(self):
        while self._running:
            try:
                port = self.port or find_port()
                if not port:
                    raise IOError("LiDAR adapter not plugged in")
                # "socket://host:port" reads a LiDAR forwarded over WiFi by a serial bridge
                opener = serial.serial_for_url(port, timeout=0.2) if "://" in port \
                    else serial.Serial(port, BAUD, timeout=0.2)
                with opener as s:
                    s.write(CMD_STOP)
                    time.sleep(0.2)
                    s.reset_input_buffer()
                    s.write(CMD_SCAN)
                    self.connected, self.error = True, ""
                    self._read_loop(s)
                    s.write(CMD_STOP)
            except Exception as e:
                self.error = str(e)
            self.connected = False
            time.sleep(1)

    def _read_loop(self, s):
        buf, current = b"", []
        last_data = time.time()
        while self._running:
            chunk = s.read(4096)
            if chunk:
                last_data = time.time()
            elif time.time() - last_data > 2:
                raise IOError("no data from LiDAR")
            buf += chunk
            gen = parse_packets(buf)
            try:
                while True:
                    new_rotation, points = next(gen)
                    if new_rotation and current:
                        with self.lock:
                            self._scan = current
                            self.scan_time = time.time()
                            self.scans += 1
                        current = []
                    current.extend(p for p in points if p[1] > 0)
            except StopIteration as done:
                buf = done.value or b""
