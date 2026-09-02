# MicroPython Drivers for Widgetlords PI-SPI Boards

MicroPython drivers for the [Widgetlords](https://widgetlords.com/) PI-SPI series of
industrial I/O modules for the Raspberry Pi Pico. Translated from the reference
C implementation in
[widgetlords/libwidgetlords](https://github.com/widgetlords/libwidgetlords).

Two modules are covered:

| File | Class | Board | Chip | Channels |
|---|---|---|---|---|
| [pi_spi_8ai.py](pi_spi_8ai.py) | `Mod8AI` | PI-SPI-8AI | MCP3208 (12-bit ADC) | 8 analog inputs (4-20 mA / 0-10 VDC) |
| [pi_spi_2ao.py](pi_spi_2ao.py) | `Mod2AO` | PI-SPI-2AO | MCP4822 (12-bit DAC) | 2 analog outputs (4-20 mA / 0-10 VDC) |

## Features

- Pure MicroPython, no external dependencies beyond `machine`.
- Raw 12-bit count access as well as mA-scaled convenience methods.
- Pre-built SPI command frames (input driver) to avoid per-call allocation.
- Optional response-validity checking on the input driver, using the
  MCP3208 null bit to detect a floating/absent bus.

## Wiring

Both drivers take explicit pin numbers for a software-selected `SPI` bus, plus
a chip-select GPIO driven manually (CS is not left to the SPI peripheral).

| Signal | Description |
|---|---|
| `sck`  | SPI clock |
| `mosi` | SPI data out (controller -> board) |
| `miso` | SPI data in (board -> controller) |
| `cs`   | Chip select, idle-high, driven low for the duration of each transfer |

Both boards are clocked SPI mode 0 (`polarity=0, phase=0`), MSB first,
8 bits/word.

---

## `Mod8AI` -- PI-SPI-8AI (8-channel analog input)

```python
from pi_spi_8ai import Mod8AI

adc = Mod8AI(spi_id=1, sck=10, mosi=11, miso=12, cs=13)

counts = adc.read_single(0)          # raw 12-bit count, channel 0
ma     = adc.read_single_ma(0)       # scaled to mA, channel 0
counts_all = adc.read_all()          # list of 8 raw counts

adc.deinit()
```

### Constructor

```python
Mod8AI(spi_id, sck, mosi, miso, cs, baudrate=100_000)
```

| Parameter | Type | Description |
|---|---|---|
| `spi_id` | int | MicroPython SPI bus id (0 or 1) |
| `sck` | int | GPIO pin number for SCK |
| `mosi` | int | GPIO pin number for MOSI |
| `miso` | int | GPIO pin number for MISO |
| `cs` | int | GPIO pin number for chip-select |
| `baudrate` | int | SPI clock speed in Hz. Default and maximum for this board: `100_000`. |

### Methods

**`read_single(channel)`**
Read one ADC channel. `channel` is clamped to `0-7`. Returns the raw
12-bit count (`0-4095`) as an int.

**`read_single_ma(channel, zero_counts=745, range_counts=4095, range_ma=20.0, zero_ma=4.0)`**
Read one channel and scale it to milliamps over a 4-20 mA range. The
default `zero_counts`/`range_counts` calibration is nominal and may need
adjusting per board/loop. Returns a float.

**`read_single_checked(channel)`**
Like `read_single()`, but also reports whether the ADC actually responded,
using the MCP3208 null bit. Returns `(counts, valid)`; `counts` is
meaningless when `valid` is `False` (floating/absent MISO).

**`read_single_ma_checked(channel, zero_counts=745, range_counts=4095, range_ma=20.0, zero_ma=4.0)`**
`read_single_ma()` plus the validity flag. Returns `(ma, valid)`.

**`read_all()`**
Read all 8 channels in sequence. Returns a list of 8 raw 12-bit counts.

**`deinit()`**
Release the SPI bus.

---

## `Mod2AO` -- PI-SPI-2AO (2-channel analog output)

```python
from pi_spi_2ao import Mod2AO

dac = Mod2AO(spi_id=1, sck=11, mosi=10, miso=12, cs=13)

dac.write_single(0, 745)     # raw 12-bit count, ~4 mA on channel 0
dac.write_single(1, 3723)    # raw 12-bit count, ~20 mA on channel 1
dac.write_single_ma(0, 12)   # ~12 mA on channel 0
dac.write_both(745, 3723)    # both channels in one call

dac.deinit()
```

### Constructor

```python
Mod2AO(spi_id, sck, mosi, miso, cs, baudrate=500_000)
```

| Parameter | Type | Description |
|---|---|---|
| `spi_id` | int | SPI bus number (0 or 1) |
| `sck` | int | GPIO pin number for SCK |
| `mosi` | int | GPIO pin number for MOSI |
| `miso` | int | GPIO pin number for MISO |
| `cs` | int | GPIO pin number for chip-select |
| `baudrate` | int | SPI clock speed in Hz. Default: `500_000`. |

### Methods

**`write_single(channel, counts)`**
Write a raw 12-bit value (`0-4095`, clamped) to `channel` (`0` or `1`).
The driver always sets the MCP4822 `BUF` (buffered reference) and `GA`
(1x gain, 0-2.048 V full-scale internal reference) bits, and keeps the
channel active (`SHDN=1`).

**`write_single_ma(channel, ma)`**
Write output current directly in mA, clamped to `4.0-20.0`. Converted to
counts using the module-level `MA4` / `MA20` calibration constants
(`745` / `3723`).

**`write_both(counts_ch0, counts_ch1)`**
Write raw counts to both channels sequentially.

**`deinit()`**
Release the SPI bus.

### Calibration constants

```python
MA4  = 745    # 12-bit count corresponding to 4 mA
MA20 = 3723   # 12-bit count corresponding to 20 mA
```

Adjust these at the module level if a board needs per-unit calibration.

---

## Notes

- Neither driver owns the SPI pins exclusively at the bus level -- CS is
  toggled manually around each transfer, so multiple devices can share an
  SPI bus with distinct CS pins.
- `Mod8AI` is single-ended only (matching the source board's wiring of the
  MCP3208), returning raw 12-bit counts in the `0-4095` range.
- The 4-20 mA scaling on both drivers is a linear map between two
  calibration points and may need tuning against a reference meter for
  precise current-loop applications.
