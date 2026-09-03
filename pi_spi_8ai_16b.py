"""
MicroPython driver for the Widgetlords PI-SPI-8AI-16B
8-Channel 16-bit Analog Input Module (4-20 mA / 0-6.6 VDC / 10K thermistor)

ADC chip: MCP33131 (16-bit)

Translated from:
  https://github.com/widgetlords/libwidgetlords/blob/master/src/pi_spi_8ai_16b.c
  https://github.com/widgetlords/libwidgetlords/blob/master/src/spi.c

"""

from machine import SPI, Pin

_SPI_BAUDRATE = 100_000  # MAX_SPI_FREQ for this board

# Front-end scaling for the standard 4-20 mA build: the ADC spans 0-3300 mV
# across a 150 ohm load resistor, so full scale (65535 counts) is 22.0 mA.
# Retune these for the 0-6.6 VDC or 10K thermistor variants (solder jumpers) by
# editing them here -- FULL_SCALE_MA is bound into read_single_ma()'s default
# argument at import time, so reassigning it at runtime has no effect.
VREF_MV = 3300
SHUNT_OHMS = 150
FULL_SCALE_MA = VREF_MV / SHUNT_OHMS  # 22.0 mA at 65535 counts


class Mod8AI16B:
    """
    Driver for the Widgetlords PI-SPI-8AI-16B 8-channel analog input module.
    ADC: MCP33131 (16-bit).

    Unlike the 8-channel MCP3208 on the PI-SPI-8AI, this board pairs a
    single-channel ADC with an input multiplexer that is latched from the
    bytes clocked out on MOSI.  A transfer therefore *selects* a channel and
    returns the conversion of a *previously* selected one, so a reading costs
    three 2-byte transfers: one to write the mux, one to let the ADC update,
    one to fetch the result.

    Parameters
    ----------
    spi_id : int
        MicroPython SPI bus id (0 or 1).
    sck : int
        GPIO pin number for SCK.
    mosi : int
        GPIO pin number for MOSI.
    miso : int
        GPIO pin number for MISO.
    cs : int
        GPIO pin number for chip-select.
    baudrate : int
        SPI clock speed in Hz (default 100 000, max for this board).
    """

    def __init__(self, spi_id: int, sck: int, mosi: int, miso: int, cs: int,
                 baudrate: int = _SPI_BAUDRATE):
        self._cs = Pin(cs, Pin.OUT, value=1)  # CS idle-high
        self._spi = SPI(
            spi_id,
            baudrate=baudrate,
            polarity=0,
            phase=0,
            bits=8,
            firstbit=SPI.MSB,
            sck=Pin(sck),
            mosi=Pin(mosi),
            miso=Pin(miso),
        )
        self._buf = bytearray(2)
        self._channel = 0
        # Precompute the 2-byte frame for each channel so the transfer path
        # doesn't allocate on every call.
        self._tx_frames = [bytes([ch, ch]) for ch in range(8)]

    def _transfer(self, channel: int) -> int:
        """One 2-byte exchange: latch `channel` into the mux, return whatever
        16-bit conversion the ADC happens to have ready (big-endian)."""
        cs = self._cs
        buf = self._buf

        cs.low()
        self._spi.write_readinto(self._tx_frames[channel], buf)
        cs.high()

        return (buf[0] << 8) | buf[1]

    def set_channel(self, channel: int) -> None:
        """
        Select the input channel and let the ADC settle on it.

        Costs two transfers -- one to write the mux, one to ensure the ADC has
        updated -- after which `read()`, called bare, returns valid data for
        this channel.

        Parameters
        ----------
        channel : int
            Input channel to select: 0-7 (clamped).
        """
        channel = max(0, min(channel, 7))
        self._channel = channel

        # read once to write channel to mux
        self._transfer(channel)
        # read twice to ensure ADC has updated reading
        self._transfer(channel)

    def read(self, channel: int = None) -> int:
        """
        Read a channel.

        Parameters
        ----------
        channel : int or None
            Input channel to read: 0-7 (clamped).  Selects the channel first,
            costing the full three-transfer sequence, so it is correct
            whatever the mux was last left on.

            Pass None (the default) to read whichever channel is currently
            selected in a single transfer -- the fast path for polling one
            channel, valid only once `set_channel()` or an earlier
            `read(channel)` has selected it.

        Returns
        -------
        int
            16-bit raw ADC count (0-65535).
        """
        if channel is not None:
            self.set_channel(channel)
        return self._transfer(self._channel)

    def read_single(self, channel: int) -> int:
        """
        Read one ADC channel, selecting it first.

        Equivalent to `read(channel)`; kept for naming parity with
        `Mod8AI.read_single()`.

        Parameters
        ----------
        channel : int
            Input channel to read: 0-7.

        Returns
        -------
        int
            16-bit raw ADC count (0-65535).
        """
        return self.read(channel)

    def read_single_ma(self, channel: int, zero_counts: int = 0,
                       range_counts: int = 65535,
                       range_ma: float = FULL_SCALE_MA,
                       zero_ma: float = 0.0) -> float:
        """
        Read one channel and return the value in milliamps.

        Note the calibration anchors are 0 mA and full scale (22.0 mA on the
        standard 150 ohm build) -- *not* the 4 mA / 20 mA anchors used by
        `Mod8AI.read_single_ma()` -- so don't carry that driver's
        `zero_counts` across.  A 4-20 mA loop lands at roughly 11915-59577
        counts under these defaults.

        Parameters
        ----------
        channel : int
            Input channel: 0-7.
        zero_counts : int
            ADC count corresponding to `zero_ma` (default: 0).
        range_counts : int
            ADC count corresponding to `range_ma` (default: 65535).
        range_ma : float
            Current at full scale in mA (default: VREF_MV / SHUNT_OHMS = 22.0).
        zero_ma : float
            Current at zero counts in mA (default: 0.0).

        Returns
        -------
        float
        Current in mA from the specified channel, scaled from the raw ADC count.
        This may need calibrating
        """
        counts = self.read_single(channel)
        reading = (counts - zero_counts) * (range_ma - zero_ma) / (range_counts - zero_counts) + zero_ma
        return reading

    def read_all(self) -> list:
        """
        Read all 8 channels.

        Each channel costs the full select-and-read sequence, so this is 24
        transfers (~4 ms at the default 100 kHz).

        Returns
        -------
        list of int
            16-bit raw counts for channels 0-7.
        """
        return [self.read_single(ch) for ch in range(8)]

    def deinit(self) -> None:
        """Release the SPI bus."""
        self._spi.deinit()
