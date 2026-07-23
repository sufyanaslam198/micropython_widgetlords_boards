"""
MicroPython driver for the Widgetlords PI-SPI-8AI
8-Channel 12-bit Analog Input Module (4-20 mA / 0-10 VDC)

ADC chip: MCP3208 (12-bit, 8-channel)

Translated from:
  https://github.com/widgetlords/libwidgetlords/blob/master/src/pi_spi_8ai.c
  https://github.com/widgetlords/libwidgetlords/blob/master/src/spi.c

"""

from machine import SPI, Pin

_SPI_BAUDRATE = 100_000  # MCP3208 max for this board

class Mod8AI:
    """
    Driver for the Widgetlords PI-SPI-8AI 8-channel analog input module.
    ADC: MCP3208 (12-bit, single-ended).

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
        self._buf = bytearray(3)
        # Precompute the 3-byte command frame for each channel so read_single()
        # and read_all() don't allocate/recompute bits on every call.
        self._tx_frames = [
            bytes([
                0x06 | ((ch >> 2) & 0x01),
                (ch << 6) & 0xC0,
                0x00,
            ])
            for ch in range(8)
        ]

    def read_single(self, channel: int) -> int:
        """
        Read one ADC channel.

        Parameters
        ----------
        channel : int
            Input channel to read: 0-7.

        Returns
        -------
        int
            12-bit raw ADC count (0-4095).
        """
        channel = max(0, min(channel, 7))
        cs = self._cs
        buf = self._buf

        cs.low()
        self._spi.write_readinto(self._tx_frames[channel], buf)
        cs.high()

        return ((buf[1] & 0x0F) << 8) | buf[2]

    def read_single_ma(self, channel: int, zero_counts: int = 745, 
                       range_counts: int = 4095,
                       range_ma: float = 20.0,
                       zero_ma: float = 4.0) -> float:
        """
        Read one channel and return the value in milliamps (4-20 mA range).

        Parameters
        ----------
        channel : int
            Input channel: 0-7.
        zero_counts : int
            ADC count corresponding to 4 mA (default: 745).
        range_counts : int
            ADC count corresponding to 20 mA (default: 4095).
        range_ma : float
            Maximum current in mA (default: 20.0).
        zero_ma : float
            Minimum current in mA (default: 4.0).

        Returns
        -------
        float
        Current in mA from the specified channel, scaled from the raw ADC count.
        This may need calibrating
        """
        counts = self.read_single(channel)
        reading = (counts - zero_counts) * (range_ma - zero_ma) / (range_counts - zero_counts) + zero_ma
        return reading
        

    def read_single_checked(self, channel: int):
        """Read one channel AND report whether the ADC actually responded.

        The MCP3208 always drives a *null bit* LOW immediately above the 12
        data bits.  In this 3-byte frame that null bit is ``buf[1] & 0x10``.  If
        it reads HIGH the device did not respond -- the signature of a floating
        MISO from an absent/unseated board or a dead bus -- so ``valid`` is
        False and ``counts`` is meaningless.

        Together with the normal 4-20 mA under-range check this catches both
        failure rails: a MISO that floats high trips the null bit here; one that
        floats low reads ~0 counts (under-range) at the application layer.

        Returns ``(counts, valid)``.
        """
        channel = max(0, min(channel, 7))
        cs = self._cs
        buf = self._buf

        cs.low()
        self._spi.write_readinto(self._tx_frames[channel], buf)
        cs.high()

        counts = ((buf[1] & 0x0F) << 8) | buf[2]
        valid = (buf[1] & 0x10) == 0
        return counts, valid

    def read_single_ma_checked(self, channel: int, zero_counts: int = 745,
                               range_counts: int = 4095,
                               range_ma: float = 20.0,
                               zero_ma: float = 4.0):
        """``read_single_ma()`` plus the null-bit validity flag.

        Returns ``(ma, valid)``; ``ma`` is meaningless when ``valid`` is False
        (the board did not respond).  Same scaling/args as read_single_ma().
        """
        counts, valid = self.read_single_checked(channel)
        ma = (counts - zero_counts) * (range_ma - zero_ma) / (range_counts - zero_counts) + zero_ma
        return ma, valid

    def read_all(self) -> list:
        """
        Read all 8 channels.

        Returns
        -------
        list of int
            12-bit raw counts for channels 0-7.
        """
        cs = self._cs
        spi = self._spi
        buf = self._buf
        frames = self._tx_frames
        results = []

        for ch in range(8):
            cs.low()
            spi.write_readinto(frames[ch], buf)
            cs.high()
            results.append(((buf[1] & 0x0F) << 8) | buf[2])

        return results

    def deinit(self) -> None:
        """Release the SPI bus."""
        self._spi.deinit()
