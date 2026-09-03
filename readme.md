# MicroPython Drivers for Widgetlords PI-SPI Boards

MicroPython drivers for the [Widgetlords](https://widgetlords.com/) PI-SPI series of
industrial I/O modules for the Raspberry Pi Pico. Translated from the reference
C implementation in
[widgetlords/libwidgetlords](https://github.com/widgetlords/libwidgetlords).

Three modules are covered:

| File | Class | Board | Chip | Channels |
|---|---|---|---|---|
| [pi_spi_8ai.py](pi_spi_8ai.py) | `Mod8AI` | PI-SPI-8AI | MCP3208 (12-bit ADC) | 8 analog inputs (4-20 mA / 0-10 VDC) |
| [pi_spi_8ai_16b.py](pi_spi_8ai_16b.py) | `Mod8AI16B` | PI-SPI-8AI-16B | MCP33131 (16-bit ADC) | 8 analog inputs (4-20 mA / 0-6.6 VDC / 10K thermistor) |
| [pi_spi_2ao.py](pi_spi_2ao.py) | `Mod2AO` | PI-SPI-2AO | MCP4822 (12-bit DAC) | 2 analog outputs (4-20 mA / 0-10 VDC) |

## Features

- Pure MicroPython, no external dependencies beyond `machine`.
- Raw 12-bit count access as well as mA-scaled convenience methods.
- Pre-built SPI command frames (input drivers) to avoid per-call allocation.
- Optional response-validity checking on `Mod8AI`, using the MCP3208 null
  bit to detect a floating/absent bus.

## Wiring

All three drivers take explicit pin numbers for a software-selected `SPI` bus, plus
a chip-select GPIO driven manually (CS is not left to the SPI peripheral).

| Signal | Description |
|---|---|
| `sck`  | SPI clock |
| `mosi` | SPI data out (controller -> board) |
| `miso` | SPI data in (board -> controller) |
| `cs`   | Chip select, idle-high, driven low for the duration of each transfer |

All three boards are clocked SPI mode 0 (`polarity=0, phase=0`), MSB first,
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

## `Mod8AI16B` -- PI-SPI-8AI-16B (8-channel 16-bit analog input)

```python
from pi_spi_8ai_16b import Mod8AI16B

adc = Mod8AI16B(spi_id=1, sck=10, mosi=11, miso=12, cs=13)

counts = adc.read(4)                 # raw 16-bit count, channel 4
ma     = adc.read_single_ma(0)       # scaled to mA, channel 0
counts_all = adc.read_all()          # list of 8 raw counts

adc.set_channel(3)                   # select once...
counts = adc.read()                  # ...then poll at one transfer each

adc.deinit()
```

### Constructor

```python
Mod8AI16B(spi_id, sck, mosi, miso, cs, baudrate=100_000)
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

**`set_channel(channel)`**
Select the input channel (clamped to `0-7`) and let the ADC settle on it.
Costs two transfers; afterwards `read()`, called bare, returns valid data for
that channel.

**`read(channel=None)`**
Read a channel, returning the raw 16-bit count (`0-65535`) as an int. Given a
`channel` (clamped to `0-7`) it selects it first -- the full three-transfer
sequence, so it is correct whatever the mux was last left on. Called bare, it
reads whichever channel is currently selected in a single transfer, which is
the fast path for polling but only valid after `set_channel()` or an earlier
`read(channel)`.

**`read_single(channel)`**
Equivalent to `read(channel)`; kept for naming parity with
`Mod8AI.read_single()`.

**`read_single_ma(channel, zero_counts=0, range_counts=65535, range_ma=22.0, zero_ma=0.0)`**
Read one channel and scale it to milliamps, via `read(channel)` and so three
transfers. Returns a float. Note the
calibration anchors are **0 mA and full scale**, not the 4 mA / 20 mA
anchors used by `Mod8AI.read_single_ma()` -- do not copy that driver's
`zero_counts=745` across.

**`read_all()`**
Read all 8 channels in sequence, each with its own select-and-read. Returns
a list of 8 raw 16-bit counts. 24 transfers, roughly 4 ms at 100 kHz.

**`deinit()`**
Release the SPI bus.

### Scaling constants

```python
VREF_MV       = 3300              # ADC span in mV
SHUNT_OHMS    = 150               # 4-20 mA load resistor
FULL_SCALE_MA = VREF_MV / SHUNT_OHMS   # 22.0 mA at 65535 counts
```

`FULL_SCALE_MA` is bound into `read_single_ma()`'s default argument at import
time, so retune by editing these constants in the file (or pass `range_ma`
explicitly per call). Retuning is needed for the 0-6.6 VDC or 10K thermistor
channel variants, which are selected by solder jumpers on the rear of the board.

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

- No driver owns the SPI pins exclusively at the bus level -- CS is
  toggled manually around each transfer, so multiple devices can share an
  SPI bus with distinct CS pins.
- `Mod8AI` is single-ended only (matching the source board's wiring of the
  MCP3208), returning raw 12-bit counts in the `0-4095` range.
- The two input drivers differ in how a reading is obtained. The MCP3208 on
  the PI-SPI-8AI addresses its channel within a single frame, so one transfer
  is one reading. The PI-SPI-8AI-16B pairs a single-channel MCP33131 with an
  input multiplexer latched from the bytes clocked out on MOSI: a transfer
  selects a channel and returns the conversion of a previously selected one,
  so a reading takes three transfers (mux latch, settle, read).
- `Mod8AI` offers validity checking only because the MCP3208 emits a
  protocol-guaranteed null bit in its frame. The MCP33131 frame is 16 data
  bits with no reserved bit, so `Mod8AI16B` has no equivalent check --
  an under-range reading at the application layer is the only failure signal.
- The 4-20 mA scaling on all three drivers is a linear map between two
  calibration points and may need tuning against a reference meter for
  precise current-loop applications. When tested with a Fluke 707, most of
  the input boards are within 0.02mA from the factory using the above defaults.
  They do vary from channel to channel, so don't just assume one for the whole board.
