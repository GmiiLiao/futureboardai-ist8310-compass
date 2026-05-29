# main.py - Future Board AI IST8310 Compass Display
# 
# Features:
# 1. Reads IST8310 magnetometer via I2C
# 2. Reads onboard IMU (accelerometer/gyroscope)
# 3. Calculates tilt-compensated heading (true compass)
# 4. Displays values on Future Board screen
# 5. Handles KittenBlock serial protocol for extension integration
#
# Hardware: Future Board AI (ESP32-S3-FN8)
# External: IST8310 magnetometer on I2C port

from future import *
from machine import I2C, Pin
import math
import time
import sys
import ujson

# ─────────────────────────────────────────────
# I2C Setup (Future Board AI I2C port)
# SCL: GPIO4, SDA: GPIO5 (standard for Future Board)
# ─────────────────────────────────────────────
try:
    i2c = I2C(0, scl=Pin(4), sda=Pin(5), freq=400000)
except:
    try:
        i2c = I2C(1, scl=Pin(22), sda=Pin(21), freq=400000)
    except:
        i2c = I2C(0, freq=400000)

# Scan I2C bus
devices = i2c.scan()

# ─────────────────────────────────────────────
# Import IST8310 driver (must be uploaded)
# ─────────────────────────────────────────────
ist = None
try:
    from ist8310 import IST8310
    ist = IST8310(i2c)
    print("IST8310 initialized OK, WAI=0x{:02X}".format(ist.who_am_i()))
except Exception as e:
    print("IST8310 init error:", e)

# ─────────────────────────────────────────────
# Calibration offsets (hard-iron correction)
# Run calibration routine to update these values
# ─────────────────────────────────────────────
mag_offset_x = 0.0
mag_offset_y = 0.0
mag_offset_z = 0.0
mag_scale_x  = 1.0
mag_scale_y  = 1.0
mag_scale_z  = 1.0

# ─────────────────────────────────────────────
# Complementary filter state
# ─────────────────────────────────────────────
ALPHA = 0.98   # Gyro weight (0.98 = 98% gyro, 2% accel)
filt_pitch = 0.0
filt_roll  = 0.0
last_time  = time.ticks_ms()

# ─────────────────────────────────────────────
# State variables
# ─────────────────────────────────────────────
heading     = 0.0
mag_x = mag_y = mag_z = 0.0
calibrating = False
cal_samples_x = []
cal_samples_y = []
cal_samples_z = []

# ─────────────────────────────────────────────
# Helper: signed heading 0-360
# ─────────────────────────────────────────────
def normalize_heading(h):
    """Normalize heading to 0-359.9 degrees."""
    h = h % 360
    if h < 0:
        h += 360
    return h

def compass_direction(h):
    """Return cardinal direction string."""
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    idx = int((h + 22.5) / 45) % 8
    return dirs[idx]

# ─────────────────────────────────────────────
# Draw compass needle
# ─────────────────────────────────────────────
def draw_compass_needle(cx, cy, radius, angle_deg, color):
    """Draw a compass needle at angle on screen."""
    rad = math.radians(angle_deg - 90)  # 0° = up
    nx = int(cx + radius * math.cos(rad))
    ny = int(cy + radius * math.sin(rad))
    # Draw needle line
    screen.line(cx, cy, nx, ny, color)
    # Draw arrowhead
    for r in range(3):
        screen.circle(nx, ny, r, color, fill=False)

# ─────────────────────────────────────────────
# Update compass calculation
# ─────────────────────────────────────────────
def update_compass():
    global filt_pitch, filt_roll, last_time
    global heading, mag_x, mag_y, mag_z

    # ── Accelerometer data ──
    ax = sensor.accX()  # g units
    ay = sensor.accY()
    az = sensor.accZ()

    # ── Gyroscope data (°/s) ──
    # Future Board uses built-in sensor API
    gx = sensor.roll()   # roll angle in degrees
    gy = sensor.pitch()  # pitch angle in degrees

    # ── Time delta ──
    now = time.ticks_ms()
    dt = time.ticks_diff(now, last_time) / 1000.0  # seconds
    last_time = now
    if dt <= 0 or dt > 1.0:
        dt = 0.05

    # ── Compute pitch/roll from accelerometer ──
    # pitch: rotation around Y axis
    acc_pitch = math.atan2(ax, math.sqrt(ay*ay + az*az))
    # roll: rotation around X axis
    acc_roll  = math.atan2(-ay, az)

    # ── Complementary filter (blend gyro angle with accel) ──
    # sensor.pitch/roll already gives integrated angle in degrees
    filt_pitch = math.radians(gy)
    filt_roll  = math.radians(gx)

    # ── Read magnetometer ──
    if ist is None:
        return

    try:
        mx_raw, my_raw, mz_raw = ist.read_uT()
    except Exception as e:
        print("Mag read error:", e)
        return

    # Apply hard-iron calibration
    mx = (mx_raw - mag_offset_x) * mag_scale_x
    my = (my_raw - mag_offset_y) * mag_scale_y
    mz = (mz_raw - mag_offset_z) * mag_scale_z

    mag_x, mag_y, mag_z = mx, my, mz

    # ── Tilt-compensated heading calculation ──
    # Reference: https://www.nxp.com/docs/en/application-note/AN4248.pdf
    pitch = filt_pitch
    roll  = filt_roll

    cos_p = math.cos(pitch)
    sin_p = math.sin(pitch)
    cos_r = math.cos(roll)
    sin_r = math.sin(roll)

    # Project magnetometer into horizontal plane
    xh = mx * cos_p + my * sin_r * sin_p + mz * cos_r * sin_p
    yh = my * cos_r - mz * sin_r

    # Calculate heading
    h = math.atan2(-yh, xh)  # negative yh for NED convention
    heading = normalize_heading(math.degrees(h))

# ─────────────────────────────────────────────
# Draw the main UI
# ─────────────────────────────────────────────
def draw_ui():
    # Clear screen
    screen.fill((0, 0, 20))  # Dark navy background

    # ── Title bar ──
    screen.rect(0, 0, 160, 16, (0, 80, 180), fill=True)
    screen.text("IST8310 Compass", 5, 3, 1, (255, 255, 255))

    # ── Compass rose (center: 80, 68, radius 35) ──
    cx, cy, r = 80, 72, 38

    # Outer circle
    screen.circle(cx, cy, r, (100, 100, 100), fill=False)
    screen.circle(cx, cy, r-2, (60, 60, 60), fill=False)

    # Cardinal direction markers
    dirs_pos = [
        ('N', cx, cy-r+4, (255, 80, 80)),
        ('S', cx, cy+r-10, (200, 200, 200)),
        ('E', cx+r-8, cy-4, (200, 200, 200)),
        ('W', cx-r+2, cy-4, (200, 200, 200)),
    ]
    for label, lx, ly, col in dirs_pos:
        screen.text(label, lx-3, ly, 1, col)

    # Tick marks
    for deg in range(0, 360, 30):
        rad = math.radians(deg - 90)
        x1 = int(cx + (r-2) * math.cos(rad))
        y1 = int(cy + (r-2) * math.sin(rad))
        x2 = int(cx + (r-8) * math.cos(rad))
        y2 = int(cy + (r-8) * math.sin(rad))
        screen.line(x1, y1, x2, y2, (120, 120, 120))

    # North needle (red)
    draw_compass_needle(cx, cy, r-12, heading, (220, 50, 50))
    # South indicator (white)
    draw_compass_needle(cx, cy, r-22, heading + 180, (200, 200, 200))

    # Center dot
    screen.circle(cx, cy, 3, (255, 200, 0), fill=True)

    # ── Data display ──
    # Heading
    dir_str = compass_direction(heading)
    screen.text("HDG: {:.1f} {}".format(heading, dir_str), 5, 118, 1, (255, 200, 0))

    # Mag raw values
    screen.text("Mx:{:6.1f}".format(mag_x), 2, 4, 1, (100, 200, 100))
    screen.text("My:{:6.1f}".format(mag_y), 55, 4, 1, (100, 200, 100))
    screen.text("Mz:{:6.1f}".format(mag_z), 108, 4, 1, (100, 200, 100))

    # Pitch/Roll
    screen.text("P:{:.0f} R:{:.0f}".format(
        math.degrees(filt_pitch), math.degrees(filt_roll)), 5, 109, 1, (150, 150, 255))

    # Refresh display
    screen.refresh()

# ─────────────────────────────────────────────
# KittenBlock serial protocol handler
# Responds to commands from KittenBlock extension
# Protocol: JSON lines over USB serial
# ─────────────────────────────────────────────
def check_serial():
    """Check for incoming serial commands from KittenBlock."""
    if sys.stdin in []:  # Non-blocking check
        return
    try:
        # Non-blocking readline
        import select
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if not r:
            return
        line = sys.stdin.readline().strip()
        if not line:
            return
        handle_command(line)
    except:
        pass

def handle_command(cmd):
    """Handle serial command from KittenBlock extension."""
    global calibrating, cal_samples_x, cal_samples_y, cal_samples_z
    global mag_offset_x, mag_offset_y, mag_offset_z

    try:
        data = ujson.loads(cmd)
        action = data.get('action', '')

        if action == 'getHeading':
            response = {'heading': round(heading, 1), 'dir': compass_direction(heading)}
            print(ujson.dumps(response))

        elif action == 'getMag':
            response = {'mx': round(mag_x, 2), 'my': round(mag_y, 2), 'mz': round(mag_z, 2)}
            print(ujson.dumps(response))

        elif action == 'getPitchRoll':
            response = {'pitch': round(math.degrees(filt_pitch), 1),
                       'roll': round(math.degrees(filt_roll), 1)}
            print(ujson.dumps(response))

        elif action == 'startCalibration':
            calibrating = True
            cal_samples_x = []
            cal_samples_y = []
            cal_samples_z = []
            print('{"status":"calibrating"}')

        elif action == 'stopCalibration':
            if cal_samples_x:
                mag_offset_x = (max(cal_samples_x) + min(cal_samples_x)) / 2
                mag_offset_y = (max(cal_samples_y) + min(cal_samples_y)) / 2
                mag_offset_z = (max(cal_samples_z) + min(cal_samples_z)) / 2
            calibrating = False
            response = {'status': 'done', 'ox': mag_offset_x, 'oy': mag_offset_y, 'oz': mag_offset_z}
            print(ujson.dumps(response))

        elif action == 'ping':
            print('{"status":"ok","device":"FutureBoard_IST8310"}')

    except Exception as e:
        print('{{"error":"{}"}}'.format(str(e)))

# ─────────────────────────────────────────────
# Calibration sample collection
# ─────────────────────────────────────────────
def collect_cal_sample():
    if calibrating and ist:
        try:
            mx, my, mz = ist.read_uT()
            cal_samples_x.append(mx)
            cal_samples_y.append(my)
            cal_samples_z.append(mz)
        except:
            pass

# ─────────────────────────────────────────────
# Button A: Start/stop calibration
# ─────────────────────────────────────────────
def on_btn_a():
    global calibrating
    if not calibrating:
        calibrating = True
        cal_samples_x.clear()
        cal_samples_y.clear()
        cal_samples_z.clear()
        screen.fill((0, 0, 0))
        screen.text("Calibrating...", 10, 50, 1, (255, 200, 0))
        screen.text("Rotate device", 10, 65, 1, (200, 200, 200))
        screen.text("in all directions", 5, 80, 1, (200, 200, 200))
        screen.text("Press B to finish", 5, 95, 1, (100, 255, 100))
        screen.refresh()
    else:
        calibrating = False

def on_btn_b():
    global calibrating, mag_offset_x, mag_offset_y, mag_offset_z
    if calibrating and cal_samples_x:
        mag_offset_x = (max(cal_samples_x) + min(cal_samples_x)) / 2
        mag_offset_y = (max(cal_samples_y) + min(cal_samples_y)) / 2
        mag_offset_z = (max(cal_samples_z) + min(cal_samples_z)) / 2
        calibrating = False
        screen.fill((0, 0, 0))
        screen.text("Cal complete!", 10, 55, 1, (100, 255, 100))
        screen.text("Offset X: {:.1f}".format(mag_offset_x), 5, 70, 1, (200, 200, 200))
        screen.text("Offset Y: {:.1f}".format(mag_offset_y), 5, 82, 1, (200, 200, 200))
        screen.text("Offset Z: {:.1f}".format(mag_offset_z), 5, 94, 1, (200, 200, 200))
        screen.refresh()
        time.sleep(2)

# Button event handlers
button[0].irq(trigger=Pin.IRQ_FALLING, handler=lambda p: on_btn_a())
button[1].irq(trigger=Pin.IRQ_FALLING, handler=lambda p: on_btn_b())

# ─────────────────────────────────────────────
# Disable screen auto-refresh for smoother updates
# ─────────────────────────────────────────────
screen.sync = 0

# ─────────────────────────────────────────────
# Show startup screen
# ─────────────────────────────────────────────
screen.fill((0, 0, 20))
screen.text("IST8310 Compass", 10, 40, 1, (255, 200, 0))
screen.text("Initializing...", 15, 60, 1, (200, 200, 200))
if ist:
    screen.text("Sensor: OK", 25, 75, 1, (100, 255, 100))
else:
    screen.text("Sensor: ERROR", 20, 75, 1, (255, 80, 80))
screen.text("I2C devices:", 5, 90, 1, (150, 150, 255))
screen.text(str([hex(d) for d in devices]), 5, 102, 1, (150, 255, 150))
screen.refresh()
time.sleep(2)

# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────
loop_count = 0
while True:
    try:
        if calibrating:
            collect_cal_sample()
            time.sleep_ms(50)
        else:
            # Update compass every 100ms
            update_compass()
            draw_ui()
            check_serial()

        loop_count += 1

    except KeyboardInterrupt:
        break
    except Exception as e:
        screen.fill((50, 0, 0))
        screen.text("Error:", 5, 50, 1, (255, 100, 100))
        screen.text(str(e)[:20], 5, 65, 1, (255, 200, 200))
        screen.refresh()
        time.sleep(1)
