# IST8310 Compass for Future Board AI

A complete solution for reading the **IST8310 3-axis magnetometer** via I2C on the **Future Board AI (ESP32-S3)**, with tilt-compensated compass heading and a KittenBlock extension.

## Hardware Setup

| Connection | Detail |
|------------|--------|
| Device | Future Board AI (FutureLite ESP32-S3-FN8) |
| Sensor | IST8310 3-axis magnetometer |
| Interface | I2C (SCL: GPIO4, SDA: GPIO5) |
| I2C Address | 0x0E |
| Sensitivity | 0.3 µT/LSB |

## Features

- ✅ IST8310 magnetometer driver (MicroPython)
- ✅ Display XYZ magnetometer values on screen
- ✅ Tilt-compensated compass heading using built-in IMU
- ✅ Complementary filter (gyroscope + accelerometer)
- ✅ Hard-iron calibration (press A to calibrate, B to finish)
- ✅ KittenBlock extension (kblock.kittenblock.cc)
- ✅ JSON serial protocol for KittenBlock communication

## Files

```
futureboardai-ist8310-compass/
├── micropython/
│   ├── ist8310.py      # IST8310 sensor driver
│   └── main.py         # Main program (display + compass)
└── kittenblock-extension/
    ├── index.js        # KittenBlock extension
    └── manifest.json   # Extension metadata
```

## Upload to Future Board AI

```bash
# Upload the IST8310 driver
mpremote connect /dev/cu.usbmodem1234561 cp micropython/ist8310.py :

# Upload the main program
mpremote connect /dev/cu.usbmodem1234561 cp micropython/main.py :

# Reset the board
mpremote connect /dev/cu.usbmodem1234561 reset
```

## KittenBlock Extension Blocks

| Block | Type | Description |
|-------|------|-------------|
| Connect IST8310 compass | Command | Initialize connection |
| compass connected? | Boolean | Check if sensor is responding |
| compass heading (°) | Reporter | Get tilt-compensated heading 0-360° |
| compass direction | Reporter | N/NE/E/SE/S/SW/W/NW |
| facing [DIR]? | Boolean | Check if pointing a direction |
| heading between [MIN] and [MAX] °? | Boolean | Range check |
| magnetometer X/Y/Z (µT) | Reporter | Raw mag values |
| magnetic field strength (µT) | Reporter | Total field magnitude |
| pitch angle (°) | Reporter | Tilt angle front-back |
| roll angle (°) | Reporter | Tilt angle left-right |
| start calibration | Command | Start hard-iron calibration |
| stop calibration and save | Command | Finish calibration |
| update compass data | Command | Force sensor update |

## Compass Heading Algorithm

The heading uses a **tilt-compensated** calculation:

1. **Get pitch/roll** from Future Board's built-in IMU (sensor.pitch(), sensor.roll())
2. **Project magnetometer** into horizontal plane using rotation matrix:
   ```
   Xh = Mx·cos(pitch) + My·sin(roll)·sin(pitch) + Mz·cos(roll)·sin(pitch)
   Yh = My·cos(roll) - Mz·sin(roll)
   ```
3. **Calculate heading**: `atan2(-Yh, Xh)` → normalized to 0-360°

## Calibration

Press **Button A** on Future Board to start calibration:
1. Rotate the device slowly in all directions (figure-8 motion)
2. Press **Button B** to finish and save offsets

Hard-iron offsets are calculated as: `offset = (max + min) / 2` for each axis.

## License

MIT
