# Plant moisture monitor: capacitive v1.2 sensor on 5V, AOUT through a
# divider into A0 (GP26). Mood shows as a face on the LOLIN 8x8 matrix
# (TM1640: CLK on D4/GP6, DIN on D5/GP7) and as a colour on the onboard
# NeoPixel. Faces come from the original Arduino sketch.
import time

import neopixel
from machine import ADC, Pin

DRY_RAW = 1600  # probe in air
WET_RAW = 1148  # probe in water
BRIGHTNESS = 4  # TM1640 0..7
ROTATE_180 = True  # matrix mounted upside down

FACES = {
    "happy": [
        "........", ".##..##.", ".##..##.", "........",
        "#......#", ".#....#.", "..####..", "........",
    ],
    "neutral": [
        "........", ".##..##.", ".##..##.", "........",
        "........", "..####..", "........", "........",
    ],
    "thirsty": [
        "........", ".##..##.", ".##..##.", "........",
        "..####..", ".#....#.", "#......#", "........",
    ],
    "soggy": [
        "........", ".##..##.", ".##..##.", "........",
        "........", ".#.#.#..", "#.#.#.#.", "........",
    ],
    "drop": [
        "...##...", "...##...", "..####..", ".######.",
        ".######.", ".######.", "..####..", "........",
    ],
}
COLOURS = {
    "thirsty": (40, 0, 0),
    "neutral": (30, 20, 0),
    "happy": (0, 40, 0),
    "soggy": (0, 0, 40),
}


class TM1640:
    def __init__(self, clk, din):
        self.clk = Pin(clk, Pin.OUT, value=1)
        self.din = Pin(din, Pin.OUT, value=1)

    def _start(self):
        self.din(0)
        time.sleep_us(2)
        self.clk(0)

    def _stop(self):
        self.din(0)
        self.clk(1)
        time.sleep_us(2)
        self.din(1)

    def _byte(self, b):
        for i in range(8):
            self.din((b >> i) & 1)
            time.sleep_us(1)
            self.clk(1)
            time.sleep_us(1)
            self.clk(0)

    def _cmd(self, b):
        self._start()
        self._byte(b)
        self._stop()

    def show(self, rows, brightness=BRIGHTNESS):
        self._cmd(0x40)  # write data, auto-increment address
        self._start()
        self._byte(0xC0)  # start at address 0
        for r in rows:
            self._byte(r)
        self._stop()
        self._cmd(0x88 | (brightness & 7))  # display on


def bitmap(face):
    if ROTATE_180:
        face = ["".join(reversed(row)) for row in reversed(face)]
    return [sum(1 << c for c in range(8) if row[c] == "#") for row in face]


BITMAPS = {k: bitmap(v) for k, v in FACES.items()}

adc = ADC(26)
matrix = TM1640(6, 7)
Pin(11, Pin.OUT, value=1)  # onboard NeoPixel power
led = neopixel.NeoPixel(Pin(12), 1)


def read_raw():
    return sum(adc.read_u16() >> 4 for _ in range(16)) // 16


def percent(raw):
    pct = (DRY_RAW - raw) * 100 // (DRY_RAW - WET_RAW)
    return max(0, min(100, pct))


def mood(pct):
    if pct > 84:
        return "soggy"
    if pct >= 40:
        return "happy"
    if pct > 20:
        return "neutral"
    return "thirsty"


matrix.show(BITMAPS["drop"])
time.sleep(1)
last_pct = None
while True:
    raw = read_raw()
    pct = percent(raw)
    m = mood(pct)
    if last_pct is not None and pct - last_pct >= 15:
        matrix.show(BITMAPS["drop"])  # just watered
        time.sleep(2)
    matrix.show(BITMAPS[m])
    led[0] = COLOURS[m]
    led.write()
    print("raw", raw, " moisture", pct, "%  ->", m)
    last_pct = pct
    time.sleep(2)
