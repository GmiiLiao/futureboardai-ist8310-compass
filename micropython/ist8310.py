# IST8310 3-axis magnetometer driver for MicroPython
# Compatible with Future Board AI (ESP32-S3)
# I2C Address: 0x0E

import time

class IST8310:
    """Driver for the IST8310 3-axis digital magnetometer."""

    # I2C address
    I2C_ADDR = 0x0E

    # Registers
    REG_WAI      = 0x00  # Who Am I - should return 0x10
    REG_STAT1    = 0x02  # Status register 1 (DRDY bit)
    REG_DATAXL   = 0x03  # X-axis data Low byte
    REG_DATAXH   = 0x04  # X-axis data High byte
    REG_DATAYL   = 0x05  # Y-axis data Low byte
    REG_DATAYH   = 0x06  # Y-axis data High byte
    REG_DATAZL   = 0x07  # Z-axis data Low byte
    REG_DATAZH   = 0x08  # Z-axis data High byte
    REG_STAT2    = 0x09  # Status register 2
    REG_CNTL1   = 0x0A  # Control register 1
    REG_CNTL2   = 0x0B  # Control register 2
    REG_STR      = 0x0C  # Self test register
    REG_TEMPL    = 0x1C  # Temperature Low byte
    REG_TEMPH    = 0x1D  # Temperature High byte
    REG_TCCNTL   = 0x40  # Temperature compensation control
    REG_PDCNTL   = 0x42  # Pulse duration control

    # CNTL1 measurement modes
    MODE_STANDBY    = 0x00
    MODE_SINGLE     = 0x01
    MODE_CONT_10HZ  = 0x02
    MODE_CONT_20HZ  = 0x06

    # Sensitivity: 0.3 µT/LSB
    SENSITIVITY = 0.3

    def __init__(self, i2c, addr=I2C_ADDR):
        self.i2c = i2c
        self.addr = addr
        self._init_sensor()

    def _read_reg(self, reg):
        """Read a single byte from register."""
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _write_reg(self, reg, val):
        """Write a single byte to register."""
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _init_sensor(self):
        """Initialize the IST8310 sensor."""
        # Verify device ID
        wai = self._read_reg(self.REG_WAI)
        if wai != 0x10:
            raise RuntimeError(f"IST8310 not found! WAI=0x{wai:02X}, expected 0x10")

        # Software reset
        self._write_reg(self.REG_CNTL2, 0x01)
        time.sleep_ms(10)

        # Set pulse duration for performance
        self._write_reg(self.REG_PDCNTL, 0xC0)
        time.sleep_ms(5)

        # Enable temperature compensation
        self._write_reg(self.REG_TCCNTL, 0x00)
        time.sleep_ms(5)

    def _read_raw(self):
        """Trigger measurement and read raw XYZ data."""
        # Trigger single measurement
        self._write_reg(self.REG_CNTL1, self.MODE_SINGLE)

        # Wait for data ready (DRDY bit in STAT1)
        timeout = 50  # 50ms timeout
        while timeout > 0:
            stat = self._read_reg(self.REG_STAT1)
            if stat & 0x01:  # DRDY bit set
                break
            time.sleep_ms(1)
            timeout -= 1

        if timeout == 0:
            raise RuntimeError("IST8310: measurement timeout")

        # Burst read 6 bytes starting from DATAXL
        data = self.i2c.readfrom_mem(self.addr, self.REG_DATAXL, 6)

        # Combine bytes into signed 16-bit integers (little-endian)
        x = data[0] | (data[1] << 8)
        y = data[2] | (data[3] << 8)
        z = data[4] | (data[5] << 8)

        # Convert to signed
        if x >= 32768: x -= 65536
        if y >= 32768: y -= 65536
        if z >= 32768: z -= 65536

        return x, y, z

    def read_raw(self):
        """Return raw XYZ magnetometer values (LSB)."""
        return self._read_raw()

    def read_uT(self):
        """Return magnetometer readings in microtesla (µT)."""
        x, y, z = self._read_raw()
        return (x * self.SENSITIVITY,
                y * self.SENSITIVITY,
                z * self.SENSITIVITY)

    def who_am_i(self):
        """Return device ID register value (should be 0x10)."""
        return self._read_reg(self.REG_WAI)
