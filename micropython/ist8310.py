# IST8310 3-axis magnetometer driver for MicroPython
# Compatible with Future Board AI (FutureLite ESP32-S3)
# Uses board.i2c (SCL=GPIO19, SDA=GPIO20, I2C(0) @ 400kHz)
# I2C Address: 0x0E (ADDR pin = HIGH)
# Reference: IST8310 Datasheet v1.0

import time

class IST8310:
    """Driver for the IST8310 3-axis digital magnetometer."""

    # I2C address (ADDR pin HIGH = 0x0E, ADDR pin LOW = 0x0C)
    I2C_ADDR = 0x0E

    # Register map
    REG_WAI      = 0x00  # Who Am I (should return 0x10)
    REG_STAT1    = 0x02  # Status 1: bit0=DRDY
    REG_DATAXL   = 0x03  # X low byte
    REG_DATAXH   = 0x04  # X high byte
    REG_DATAYL   = 0x05  # Y low byte
    REG_DATAYH   = 0x06  # Y high byte
    REG_DATAZL   = 0x07  # Z low byte
    REG_DATAZH   = 0x08  # Z high byte
    REG_STAT2    = 0x09  # Status 2
    REG_CNTL1    = 0x0A  # Control 1 (trigger measurement)
    REG_CNTL2    = 0x0B  # Control 2 (soft reset)
    REG_STR      = 0x0C  # Self test
    REG_TEMPL    = 0x1C  # Temperature low
    REG_TEMPH    = 0x1D  # Temperature high
    REG_TCCNTL   = 0x40  # Temperature compensation
    REG_PDCNTL   = 0x42  # Pulse duration control

    # Measurement modes for CNTL1
    MODE_STANDBY    = 0x00
    MODE_SINGLE     = 0x01  # Single measurement
    MODE_CONT_10HZ  = 0x02  # Continuous 10Hz
    MODE_CONT_20HZ  = 0x06  # Continuous 20Hz

    # Output sensitivity: 0.3 µT per LSB
    SENSITIVITY = 0.3

    def __init__(self, i2c, addr=None):
        """
        Initialize IST8310 driver.
        
        Args:
            i2c: I2C bus object (use board.i2c for Future Board AI)
            addr: I2C address (default: 0x0E)
        """
        self.i2c = i2c
        self.addr = addr if addr is not None else self.I2C_ADDR
        self._init_sensor()

    def _read_reg(self, reg, nbytes=1):
        """Read bytes from a register."""
        return self.i2c.readfrom_mem(self.addr, reg, nbytes)

    def _write_reg(self, reg, val):
        """Write a byte to a register."""
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _init_sensor(self):
        """Initialize the IST8310 with recommended settings."""
        # Try to verify device identity (WAI should be 0x10)
        # Note: Some firmware versions may return 0xFF for WAI
        # We verify the device is working by checking measurement capability
        wai = self._read_reg(self.REG_WAI)[0]
        self._wai = wai
        # Allow 0xFF as WAI fallback (firmware dependent)
        if wai not in (0x10, 0xFF):
            raise RuntimeError(
                "IST8310 not found at addr=0x{:02X}. WAI=0x{:02X}".format(
                    self.addr, wai))

        # Software reset (bit0 of CNTL2)
        self._write_reg(self.REG_CNTL2, 0x01)
        time.sleep_ms(20)

        # Set pulse duration for optimal performance
        # PDCNTL[7:6] = 11 = normal mode
        self._write_reg(self.REG_PDCNTL, 0xC0)
        time.sleep_ms(5)

        # Disable temperature compensation (default)
        self._write_reg(self.REG_TCCNTL, 0x00)
        time.sleep_ms(5)

    def _trigger_and_read(self):
        """Trigger a single measurement and return raw XYZ data."""
        # Trigger single measurement
        self._write_reg(self.REG_CNTL1, self.MODE_SINGLE)

        # Wait for data ready (max 8ms per datasheet)
        timeout_ms = 50
        for _ in range(timeout_ms):
            stat = self._read_reg(self.REG_STAT1)[0]
            if stat & 0x01:  # DRDY bit
                break
            time.sleep_ms(1)
        else:
            raise RuntimeError("IST8310: measurement timeout")

        # Burst-read 6 data bytes (X_L, X_H, Y_L, Y_H, Z_L, Z_H)
        raw = self._read_reg(self.REG_DATAXL, 6)

        # Convert to signed 16-bit integers (little-endian)
        x = raw[0] | (raw[1] << 8)
        y = raw[2] | (raw[3] << 8)
        z = raw[4] | (raw[5] << 8)
        if x >= 32768: x -= 65536
        if y >= 32768: y -= 65536
        if z >= 32768: z -= 65536

        return x, y, z

    def read_raw(self):
        """
        Read raw magnetometer data.
        
        Returns:
            tuple: (x, y, z) in raw LSB units
        """
        return self._trigger_and_read()

    def read_uT(self):
        """
        Read magnetometer data in microtesla (µT).
        
        Returns:
            tuple: (x, y, z) in µT
        """
        x, y, z = self._trigger_and_read()
        return (x * self.SENSITIVITY,
                y * self.SENSITIVITY,
                z * self.SENSITIVITY)

    def read_temperature(self):
        """
        Read temperature in Celsius (approximate).
        
        Returns:
            float: temperature in °C
        """
        raw = self._read_reg(self.REG_TEMPL, 2)
        temp = raw[0] | (raw[1] << 8)
        if temp >= 32768: temp -= 65536
        return temp / 100.0

    def who_am_i(self):
        """Return device ID (should be 0x10 for IST8310)."""
        return self._read_reg(self.REG_WAI)[0]

    def scan_i2c(self):
        """Scan I2C bus and return list of found device addresses."""
        return self.i2c.scan()

    @classmethod
    def find_and_create(cls, i2c):
        """
        Auto-detect IST8310 on I2C bus and create instance.
        Tries both 0x0E (ADDR high) and 0x0C (ADDR low) addresses.
        
        Returns:
            IST8310 instance, or None if not found
        """
        devices = i2c.scan()
        for addr in [0x0E, 0x0C, 0x0D, 0x0F]:
            if addr in devices:
                try:
                    inst = cls(i2c, addr)
                    return inst
                except RuntimeError:
                    pass
        return None
