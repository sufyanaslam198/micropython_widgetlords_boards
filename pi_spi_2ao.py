"""
MicroPython driver for the Widgetlords PI-SPI-2AO
2-Channel 12-bit Analog Output Module (4-20 mA / 0-10 VDC)

DAC chip: MCP4822 (12-bit)

Translated from:
  https://github.com/widgetlords/libwidgetlords/blob/master/src/pi_spi_2ao.c
  https://github.com/widgetlords/libwidgetlords/blob/master/src/spi.c

----------------------------------------------------------------------
MCP4822 SPI word format (16 bits, MSB first)

  Byte 0:  [CH | BUF | GA | SHDN | D11 | D10 | D9 | D8]
  Byte 1:  [D7 | D6  | D5 | D4   | D3  | D2  | D1 | D0]

  CH   (bit 7)  : Channel select
                  0 = DAC A
                  1 = DAC B

  BUF  (bit 6)  : VREF buffer enable
                  1 = buffered (REQUIRED for stable operation)

  GA   (bit 5)  : Gain selection
                  1 = 1x gain (0-2.048 V full-scale)
                  0 = 2x gain (0-4.096 V full-scale)

  SHDN (bit 4)  : Shutdown control
                  1 = active
                  0 = shutdown

  D11-D0        : 12-bit DAC value
  
Usage example:

    from pi_spi_2ao import Mod2AO

    dac = Mod2AO(spi_id=1, sck=11, mosi=10, miso=12, cs=13)

    dac.write_single(0, 745)    # ~4 mA
    dac.write_single(1, 3723)   # ~20 mA

    dac.write_single_ma(0, 12)  # ~12 mA

    dac.deinit()
"""

from machine import SPI, Pin

_SPI_BAUDRATE = 500_000

# 4–20 mA calibration constants (12-bit counts)
MA4  = 745
MA20 = 3723
_MA_SLOPE = (MA20 - MA4) / 16.0


class Mod2AO:
    """
    Driver for the Widgetlords PI-SPI-2AO module.

    Parameters
    ----------
    spi_id : int
        SPI bus number (0 or 1 on Pico/W)
    sck, mosi, miso : int
        GPIO pin numbers for SPI
    cs : int
        Chip select pin
    baudrate : int
        SPI clock (default 500 kHz)
    """

    def __init__(self, spi_id, sck, mosi, miso, cs,
                 baudrate=_SPI_BAUDRATE):

        self._cs = Pin(cs, Pin.OUT, value=1)

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
        self._txbuf = bytearray(2)

    def write_single(self, channel: int, counts: int) -> None:
        """
        Write raw DAC counts to a single channel.

        Parameters
        ----------
        channel : int
            0 or 1
        counts : int
            12-bit value (0-4095)
        """

        channel = 1 if channel else 0
        counts = max(0, min(0xFFF, counts))

        byte0 = (
            (channel << 7) |   # CH
            (1 << 6) |         # BUF = 1
            (1 << 5) |         # GA = 1
            (1 << 4) |         # SHDN = 1
            ((counts >> 8) & 0x0F)
        )

        byte1 = counts & 0xFF

        txbuf = self._txbuf
        txbuf[0] = byte0
        txbuf[1] = byte1
        self._transfer(txbuf)

    def write_single_ma(self, channel: int, ma: float) -> None:
        """
        Write output current directly in mA.

        Parameters
        ----------
        channel : int
            0 or 1
        ma : float
            Desired current (clamped to 4.0-20.0 mA)
        """

        ma = max(4.0, min(20.0, ma))

        counts = round(MA4 + (ma - 4.0) * _MA_SLOPE)

        self.write_single(channel, counts)

    def write_both(self, counts_ch0: int, counts_ch1: int) -> None:
        """Write both channels sequentially."""
        self.write_single(0, counts_ch0)
        self.write_single(1, counts_ch1)

    def deinit(self) -> None:
        """Release SPI bus."""
        self._spi.deinit()

    def _transfer(self, data: bytes) -> None:
        self._cs.low()
        self._spi.write(data)
        self._cs.high()

