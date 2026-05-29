# main.py - Future Board AI IST8310 Compass Display
#
# Hardware: Future Board AI (FutureLite ESP32-S3-FN8)
# External: IST8310 magnetometer on I2C(1) port (SCL=GPIO1, SDA=GPIO2)
# Internal: SC7I22 IMU (acc/gyro) on I2C(0) = board.i2c (SCL=19, SDA=20)
#
# Features:
# 1. Reads IST8310 magnetometer via I2C(1)
# 2. Reads onboard accelerometer via board.i2c for tilt angles
# 3. Calculates tilt-compensated heading (true compass)
# 4. Displays compass rose UI on Future Board screen
# 5. Button A: Start calibration | Button B: Stop calibration
# 6. Serial JSON protocol for KittenBlock extension
#
# I2C Connections:
#   IST8310: I2C(1) SCL=Pin(1), SDA=Pin(2)  - External I2C port
#   IMU SC7I22: board.i2c = I2C(0) SCL=19, SDA=20 - Internal bus

from future import *
from machine import I2C, Pin
import math
import time
import sys
import ujson
import board

# ─────────────────────────────────────────────
# IST8310 on I2C(1) - External I2C connector
# SCL=GPIO1, SDA=GPIO2
# ─────────────────────────────────────────────
ist_i2c = I2C(1, scl=Pin(1), sda=Pin(2), freq=400000)
i2c_devices = ist_i2c.scan()
print("IST I2C scan:", [hex(d) for d in i2c_devices])

# IST8310 register addresses
IST_ADDR       = 0x0E
IST_REG_STAT1  = 0x02  # Status (bit0=DRDY)
IST_REG_DATAXL = 0x03  # Data start (6 bytes)
IST_REG_CNTL1  = 0x0A  # Trigger measurement
IST_REG_CNTL2  = 0x0B  # Software reset
IST_REG_PDCNTL = 0x42  # Pulse duration
IST_SENSITIVITY = 0.3   # µT per LSB

# Initialize IST8310
ist_ok = False
if IST_ADDR in i2c_devices:
    try:
        ist_i2c.writeto_mem(IST_ADDR, IST_REG_CNTL2, bytes([0x01]))  # Soft reset
        time.sleep_ms(50)
        ist_i2c.writeto_mem(IST_ADDR, IST_REG_PDCNTL, bytes([0xC0]))  # Pulse duration
        time.sleep_ms(5)
        ist_i2c.writeto_mem(IST_ADDR, IST_REG_CNTL1, bytes([0x01]))  # Test trigger
        time.sleep_ms(15)
        stat = ist_i2c.readfrom_mem(IST_ADDR, IST_REG_STAT1, 1)[0]
        ist_ok = True
        print("IST8310 OK, STAT=0x{:02X}".format(stat))
    except Exception as e:
        print("IST8310 init err:", e)
else:
    print("IST8310 not found! Bus:", [hex(d) for d in i2c_devices])

# ─────────────────────────────────────────────
# Read IST8310 magnetometer
# ─────────────────────────────────────────────
def read_mag():
    """Return (mx, my, mz) in µT from IST8310."""
    try:
        ist_i2c.writeto_mem(IST_ADDR, IST_REG_CNTL1, bytes([0x01]))
        for _ in range(50):
            if ist_i2c.readfrom_mem(IST_ADDR, IST_REG_STAT1, 1)[0] & 0x01:
                break
            time.sleep_ms(1)
        raw = ist_i2c.readfrom_mem(IST_ADDR, IST_REG_DATAXL, 6)
        x = raw[0] | (raw[1] << 8)
        y = raw[2] | (raw[3] << 8)
        z = raw[4] | (raw[5] << 8)
        if x >= 32768: x -= 65536
        if y >= 32768: y -= 65536
        if z >= 32768: z -= 65536
        return x * IST_SENSITIVITY, y * IST_SENSITIVITY, z * IST_SENSITIVITY
    except:
        return 0.0, 0.0, 0.0

# ─────────────────────────────────────────────
# SC7I22 IMU on board.i2c (SCL=19, SDA=20)
# Provides accelerometer for tilt compensation
# Address: 0x19 (SC7I22) or 0x19 (LSM303)
# ─────────────────────────────────────────────
IMU_ADDR = 0x19
imu_i2c  = board.i2c  # I2C(0, scl=19, sda=20)
imu_ok   = False

try:
    # SC7I22 CTRL_REG1: enable accel at 25Hz, all axes
    # Note: We try but may need to use sensor.pitch/roll from future
    imu_i2c.writeto_mem(IMU_ADDR, 0x20, bytes([0x37]))
    time.sleep_ms(50)
    imu_ok = True
    print("SC7I22 IMU configured OK")
except Exception as e:
    print("IMU init note:", e)
    # Will use future library's sensor.pitch/roll instead

# ─────────────────────────────────────────────
# Read accelerometer pitch/roll
# Uses future library's sensor object if available,
# otherwise reads SC7I22 directly via board.i2c
# ─────────────────────────────────────────────
def read_pitch_roll():
    """Return (pitch_deg, roll_deg) from IMU."""
    try:
        # Use future library's sensor object (available in main.py context)
        # sensor is a global created by 'from future import *'
        p = sensor.pitch()
        r = sensor.roll()
        return float(p), float(r)
    except:
        pass
    
    try:
        # Fallback: read SC7I22 directly
        raw = imu_i2c.readfrom_mem(IMU_ADDR, 0xA8, 6)
        ax = raw[0] | (raw[1] << 8)
        ay = raw[2] | (raw[3] << 8)
        az = raw[4] | (raw[5] << 8)
        if ax >= 32768: ax -= 65536
        if ay >= 32768: ay -= 65536
        if az >= 32768: az -= 65536
        # Normalize to g (16-bit, ±2g range -> /16384)
        ax_g = ax / 16384.0
        ay_g = ay / 16384.0
        az_g = az / 16384.0
        # Calculate pitch and roll
        pitch = math.atan2(ax_g, math.sqrt(ay_g*ay_g + az_g*az_g))
        roll  = math.atan2(-ay_g, az_g)
        return math.degrees(pitch), math.degrees(roll)
    except:
        return 0.0, 0.0

# ─────────────────────────────────────────────
# Calibration state
# ─────────────────────────────────────────────
mag_offset_x = 0.0
mag_offset_y = 0.0
mag_offset_z = 0.0
calibrating   = False
cal_x = []
cal_y = []
cal_z = []

# ─────────────────────────────────────────────
# State variables
# ─────────────────────────────────────────────
heading   = 0.0
mag_x = mag_y = mag_z = 0.0
pitch_deg = 0.0
roll_deg  = 0.0
error_msg = ""

# ─────────────────────────────────────────────
# Compass helpers
# ─────────────────────────────────────────────
def normalize_heading(h):
    return h % 360

def compass_direction(h):
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    return dirs[int((h + 22.5) / 45) % 8]

def draw_needle(cx, cy, r, angle_deg, color):
    rad = math.radians(angle_deg - 90)
    nx = int(cx + r * math.cos(rad))
    ny = int(cy + r * math.sin(rad))
    screen.line(cx, cy, nx, ny, color)

# ─────────────────────────────────────────────
# Main compass update
# ─────────────────────────────────────────────
def update_compass():
    global heading, mag_x, mag_y, mag_z, pitch_deg, roll_deg, error_msg

    # Get tilt angles from IMU
    pitch_deg, roll_deg = read_pitch_roll()
    pitch_rad = math.radians(pitch_deg)
    roll_rad  = math.radians(roll_deg)

    if not ist_ok:
        error_msg = "No IST8310"
        return

    mx_raw, my_raw, mz_raw = read_mag()

    # Apply hard-iron calibration
    mx = mx_raw - mag_offset_x
    my = my_raw - mag_offset_y
    mz = mz_raw - mag_offset_z
    mag_x, mag_y, mag_z = mx, my, mz

    # Tilt-compensated heading (NXP AN4248)
    cos_p = math.cos(pitch_rad)
    sin_p = math.sin(pitch_rad)
    cos_r = math.cos(roll_rad)
    sin_r = math.sin(roll_rad)
    xh = mx * cos_p + my * sin_r * sin_p + mz * cos_r * sin_p
    yh = my * cos_r - mz * sin_r
    heading = normalize_heading(math.degrees(math.atan2(-yh, xh)))
    error_msg = ""

# ─────────────────────────────────────────────
# Screen UI
# ─────────────────────────────────────────────
def draw_ui():
    screen.fill((0, 0, 22))

    # Compass rose
    cx, cy, r = 80, 70, 40
    screen.circle(cx, cy, r, (60, 60, 130), fill=False)
    screen.circle(cx, cy, r-3, (40, 40, 80), fill=False)

    # Cardinal labels
    screen.text('N', cx-3, cy-r+2, 1, (255, 70, 70))
    screen.text('S', cx-3, cy+r-10, 1, (170, 170, 170))
    screen.text('E', cx+r-8, cy-4, 1, (170, 170, 170))
    screen.text('W', cx-r+2, cy-4, 1, (170, 170, 170))

    # Tick marks
    for deg in range(0, 360, 30):
        rad = math.radians(deg - 90)
        x1 = int(cx + (r-1)*math.cos(rad)); y1 = int(cy + (r-1)*math.sin(rad))
        x2 = int(cx + (r-7)*math.cos(rad)); y2 = int(cy + (r-7)*math.sin(rad))
        screen.line(x1, y1, x2, y2, (90, 90, 90))

    # Compass needles
    draw_needle(cx, cy, r-10, heading, (230, 50, 50))       # N (red)
    draw_needle(cx, cy, r-18, heading + 180, (200, 200, 200))  # S (white)
    screen.circle(cx, cy, 3, (255, 200, 0), fill=True)

    # Status info
    dir_str = compass_direction(heading)
    screen.text('IST8310', 2, 1, 1, (80, 160, 255))
    screen.text('{:.0f} {}'.format(heading, dir_str), 105, 58, 1, (255, 200, 0))
    screen.text('deg', 112, 69, 1, (180, 180, 60))
    screen.text('P:{:.0f} R:{:.0f}'.format(pitch_deg, roll_deg), 105, 82, 1, (140, 140, 255))

    # Mag values (bottom row)
    screen.text('X:{:5.0f}'.format(mag_x), 1, 114, 1, (70, 210, 70))
    screen.text('Y:{:5.0f}'.format(mag_y), 55, 114, 1, (70, 210, 70))
    screen.text('Z:{:5.0f}'.format(mag_z), 110, 114, 1, (70, 210, 70))

    if calibrating:
        screen.rect(0, 100, 100, 12, (0, 40, 0), fill=True)
        screen.text('CAL Samples:{}'.format(len(cal_x)), 2, 102, 1, (255, 200, 0))

    if error_msg:
        screen.text(error_msg, 2, 100, 1, (255, 80, 80))

    screen.refresh()

# ─────────────────────────────────────────────
# Calibration
# ─────────────────────────────────────────────
def collect_cal():
    if ist_ok:
        try:
            mx, my, mz = read_mag()
            cal_x.append(mx); cal_y.append(my); cal_z.append(mz)
        except: pass

def finish_cal():
    global mag_offset_x, mag_offset_y, mag_offset_z, calibrating
    if cal_x:
        mag_offset_x = (max(cal_x) + min(cal_x)) / 2
        mag_offset_y = (max(cal_y) + min(cal_y)) / 2
        mag_offset_z = (max(cal_z) + min(cal_z)) / 2
    calibrating = False
    print("Cal done: X={:.1f} Y={:.1f} Z={:.1f}".format(
        mag_offset_x, mag_offset_y, mag_offset_z))

# ─────────────────────────────────────────────
# Button polling (BTNA=Pin(15), BTNB=Pin(0))
# ─────────────────────────────────────────────
_btna = board.BTNA
_btnb = board.BTNB
_a_last = _btna.value()
_b_last = _btnb.value()

def check_buttons():
    global calibrating, _a_last, _b_last
    a = _btna.value()
    if a == 0 and _a_last == 1:
        if not calibrating:
            calibrating = True
            cal_x.clear(); cal_y.clear(); cal_z.clear()
            print("Calibration started")
    _a_last = a

    b = _btnb.value()
    if b == 0 and _b_last == 1:
        if calibrating:
            finish_cal()
            screen.fill((0, 0, 0))
            screen.text('Cal Done!', 28, 52, 1, (100, 255, 100))
            screen.text('X:{:.1f}'.format(mag_offset_x), 25, 67, 1, (180, 180, 180))
            screen.text('Y:{:.1f}'.format(mag_offset_y), 25, 79, 1, (180, 180, 180))
            screen.text('Z:{:.1f}'.format(mag_offset_z), 25, 91, 1, (180, 180, 180))
            screen.refresh()
            time.sleep(2)
    _b_last = b

# ─────────────────────────────────────────────
# KittenBlock JSON serial protocol
# ─────────────────────────────────────────────
import select

def check_serial():
    try:
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if not r: return
        line = sys.stdin.readline().strip()
        if not line: return
        data = ujson.loads(line)
        action = data.get('action', '')

        if action == 'ping':
            print('{"status":"ok","device":"FutureLite_IST8310","i2c":"0x0E"}')
        elif action == 'getHeading':
            print(ujson.dumps({'heading': round(heading, 1), 'dir': compass_direction(heading)}))
        elif action == 'getMag':
            field = math.sqrt(mag_x**2 + mag_y**2 + mag_z**2)
            print(ujson.dumps({'mx': round(mag_x, 2), 'my': round(mag_y, 2),
                               'mz': round(mag_z, 2), 'field': round(field, 2)}))
        elif action == 'getPitchRoll':
            print(ujson.dumps({'pitch': round(pitch_deg, 1), 'roll': round(roll_deg, 1)}))
        elif action == 'getAll':
            print(ujson.dumps({
                'heading': round(heading, 1), 'dir': compass_direction(heading),
                'mx': round(mag_x, 2), 'my': round(mag_y, 2), 'mz': round(mag_z, 2),
                'pitch': round(pitch_deg, 1), 'roll': round(roll_deg, 1)
            }))
        elif action == 'startCalibration':
            global calibrating
            calibrating = True; cal_x.clear(); cal_y.clear(); cal_z.clear()
            print('{"status":"calibrating"}')
        elif action == 'stopCalibration':
            finish_cal()
            print(ujson.dumps({'status': 'done',
                               'ox': round(mag_offset_x, 2),
                               'oy': round(mag_offset_y, 2),
                               'oz': round(mag_offset_z, 2)}))
    except: pass

# ─────────────────────────────────────────────
# Screen setup & splash
# ─────────────────────────────────────────────
screen.sync = 0
screen.fill((0, 0, 28))
screen.text('IST8310 Compass', 8, 33, 1, (80, 160, 255))
screen.text('Future Board AI', 8, 48, 1, (160, 160, 160))
screen.text('Sensor: {}'.format('OK' if ist_ok else 'ERROR'), 15, 65, 1,
            (100, 255, 100) if ist_ok else (255, 80, 80))
screen.text('I2C(1) SCL=1 SDA=2', 4, 82, 1, (120, 120, 160))
screen.text('{}'.format([hex(d) for d in i2c_devices[:5]]), 4, 96, 1, (100, 200, 100))
screen.text('BtnA=Cal  BtnB=Done', 2, 112, 1, (110, 110, 110))
screen.refresh()
time.sleep(2)

# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────
while True:
    try:
        check_buttons()
        if calibrating:
            collect_cal()
            screen.fill((0, 20, 0))
            screen.text('CALIBRATING', 18, 38, 1, (255, 200, 0))
            screen.text('Rotate in all', 18, 54, 1, (200, 200, 200))
            screen.text('directions', 28, 67, 1, (200, 200, 200))
            screen.text('Samples: {}'.format(len(cal_x)), 25, 82, 1, (100, 255, 100))
            screen.text('Press B to finish', 8, 98, 1, (150, 255, 150))
            if cal_x:
                mx, my, mz = read_mag()
                screen.text('X:{:.0f}'.format(mx), 5, 112, 1, (140, 200, 140))
            screen.refresh()
            time.sleep_ms(100)
        else:
            update_compass()
            draw_ui()
            check_serial()
    except KeyboardInterrupt:
        print("Stopped")
        break
    except Exception as e:
        screen.fill((50, 0, 0))
        screen.text('ERR:', 5, 50, 1, (255, 100, 100))
        screen.text(str(e)[:22], 5, 65, 1, (255, 200, 200))
        screen.refresh()
        print("Err:", e)
        time.sleep(1)
