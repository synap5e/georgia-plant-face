# georgia-plant-face

A soil-moisture monitor that shows the plant's mood as a face on an 8x8 LED
matrix. It runs on a Seeed XIAO RP2040 (USB serial `4250304D30363707`).

The board arrived running a source-less Arduino sketch. That sketch was
snapshotted, reverse-engineered for its pin map, calibration and face
bitmaps, and then replaced on 2026-10-23 with a MicroPython port that works
with the sensor and shield actually on hand.

## Hardware

- Seeed XIAO RP2040
- Capacitive Soil Moisture Sensor v1.2, a clone **without the 662K
  regulator**. See [docs/moisture-sensor-v1.2-clone.png](docs/moisture-sensor-v1.2-clone.png).
- LOLIN Matrix LED Shield v1.0.0: TM1640 chip with BSS138 level shifters.
  See [docs/lolin-matrix-shield-v1.0.0-schematic.png](docs/lolin-matrix-shield-v1.0.0-schematic.png).
- 2 resistors forming a divider of about 2/3, e.g. 10k + 22k

## Wiring

XIAO pinout, top view with USB at the top:

```
        [USB]
  D0/A0 ●     ● 5V
  D1    ●     ● GND
  D2    ●     ● 3V3
  D3    ●     ● D10
  D4    ●     ● D9
  D5    ●     ● D8
  D6    ●     ● D7
```

### Moisture sensor

| Sensor | XIAO |
|---|---|
| GND (black) | GND |
| VCC (red) | **5V** |
| AOUT (yellow) | R1 (10k) → midpoint → **A0**; R2 (22k) from the midpoint to GND |

The sensor needs **5V** and the **divider**. This clone has no regulator,
so its NE555 receives raw VCC:

- At 3.3V the NE555 doesn't oscillate, and AOUT sits at 0V.
- At 5V, AOUT reaches about 3.6V dry. That is above the RP2040's 3.3V ADC
  limit; it leaks into the chip and pulls every ADC pin high.

### LED matrix shield

The shield uses D1 mini pin names. Its left header, top to bottom (LEDs up,
labels readable), is RST, A0, D0, **D5**, D6, **D7**, D8, **3V3**. The
right header is TX, RX, D1, D2, D3, D4, **GND**, **5V**.

| Shield | XIAO |
|---|---|
| D5 (CLK) | D4 (GP6) |
| D7 (DIN) | D5 (GP7) |
| 3V3 | 3V3 |
| **5V** | **5V** |
| GND | GND |

The TM1640 runs on the shield's **5V** pin. 3V3 is only the low-side
reference for the level shifters. These are pulled up to 3V3 on the MCU
side, so D4 and D5 idle high and never see 5V. With 5V missing, the chip
runs on stray current through the shifters, giving a dim, flickery display
that drops writes. An audible hum from the matrix is normal: it comes from
the row-scanning current pulses.

## Firmware

### Current: `firmware/micropython/`

- `SEEED_XIAO_RP2040-20260824-v1.29.0.uf2`: the MicroPython build that was
  flashed.
- `main.py`: the monitor. Every 2 s it averages 16 ADC reads, converts them
  to a percentage, prints `raw N  moisture N%  -> mood` over USB serial,
  draws the face and sets the onboard NeoPixel.

| Display | When | NeoPixel |
|---|---|---|
| Water drop | 1 s at boot; 2 s when moisture jumps by ≥15 points (just watered) | — |
| Frown | thirsty, ≤20% | red |
| Flat mouth | neutral, 21–39% | amber |
| Smile | happy, 40–84% | green |
| Wavy mouth | soggy, >84% (waterlogged) | blue |

Settings at the top of `main.py`:

- `DRY_RAW = 1600` (air) and `WET_RAW = 1148` (water), measured through
  the divider. The mood thresholds are untuned guesses, because real soil
  never reads as wet as plain water.
- `BRIGHTNESS = 4`. TM1640 levels 0–7 give 1, 2, 4, 10, 11, 12, 13 and
  14/16 on-time, so levels 3–7 look nearly identical.
- `ROTATE_180 = True`, for how the matrix is mounted.

MicroPython note: string slicing with a step (`s[::-1]`) isn't supported;
use `"".join(reversed(s))`.

Flash and install:

```sh
# BOOTSEL: hold BOOT while plugging in, or open the port at 1200 baud
nix shell nixpkgs#picotool -c picotool load -x firmware/micropython/SEEED_XIAO_RP2040-20260824-v1.29.0.uf2
uvx mpremote connect /dev/ttyACM0 cp firmware/micropython/main.py :main.py + reset
```

### Original: `firmware/original-arduino/`

These files are a full 2 MB flash dump of the board as it arrived, as raw
`.bin` (offset 0 = 0x10000000) and `.uf2`. Only 0x11d00 bytes are used,
and there is no filesystem.

- sha256 of `flash-full.bin`: `5b3f6c9d165250d7d03629f82cb64a405f795383a2cc55d80eccea3ed6a9cf5a`
- Built with the arduino-pico core (earlephilhower). No source was found.

From the disassembly:

| Pin | GPIO | Role |
|---|---|---|
| D0/A0 | 26 | sensor analog in: 16-sample average at 12-bit resolution |
| D1 | 27 | sensor power, on only while reading |
| D4 | 6 | matrix CLK (bit-banged TM1640, LSB first) |
| D5 | 7 | matrix DIN |

- Moisture % = `(3100 - raw) * 100 / 1250`, clamped to 0..100. This
  assumes a working 3.3V sensor powered from D1, which doesn't apply to
  the clone above.
- Serial runs at 115200 and prints the same line format as the port, once
  at boot and then every 5 minutes.
- The face bitmaps in `main.py` are copied from this binary. Each row is
  one byte, with bit N = column N, sent top row first.

To restore the original firmware:

```sh
nix shell nixpkgs#picotool -c picotool load -x firmware/original-arduino/flash-full.uf2
```

## Tools

`tools/pin-scan.py` is a PEP 723 uv script. It disassembles an RP2040
flash dump and lists calls made with small constant arguments, which is how
the sketch's `pinMode`/`digitalWrite`/`analogRead` pins were found.

```sh
tools/pin-scan.py firmware/original-arduino/flash-full.bin 0x4000
```
