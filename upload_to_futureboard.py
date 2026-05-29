#!/usr/bin/env python3
"""
upload_to_futureboard.py
Uploads IST8310 driver and main.py to Future Board AI via USB serial.
Works around the mpremote raw REPL limitation by using direct serial communication.
"""

import serial
import time
import os
import sys

PORT = '/dev/cu.usbmodem1234561'
BAUD = 115200

def serial_connect():
    """Connect to Future Board and enter raw REPL mode."""
    ser = serial.Serial(PORT, BAUD, timeout=2)
    time.sleep(0.3)
    
    # Interrupt any running program (Ctrl+C)
    ser.write(b'\r\x03\x03')
    time.sleep(0.3)
    
    # Enter normal REPL mode (Ctrl+B)
    ser.write(b'\r\x02')
    time.sleep(0.3)
    
    # Read response
    resp = ser.read_all()
    print(f"[Connect] Board response: {repr(resp[-50:])}")
    
    if b'>>>' not in resp:
        print("[ERROR] Could not get REPL prompt!")
        ser.close()
        return None
    
    # Enter Raw REPL mode (Ctrl+A)
    ser.write(b'\x01')
    time.sleep(0.3)
    resp = ser.read_all()
    
    if b'raw REPL' not in resp:
        print("[ERROR] Could not enter raw REPL!")
        ser.close()
        return None
    
    print("[OK] Raw REPL mode entered")
    return ser

def raw_repl_exec(ser, code):
    """Execute code in raw REPL mode and return output."""
    # Send code followed by Ctrl+D to execute
    ser.write(code.encode('utf-8') + b'\x04')
    time.sleep(0.5)
    
    # Read output (format: OK<output>\x04<error>\x04)
    output = b''
    start = time.time()
    while time.time() - start < 5:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            output += chunk
            if output.count(b'\x04') >= 2:
                break
        time.sleep(0.05)
    
    return output

def upload_file(ser, local_path, remote_name):
    """Upload a file to the Future Board filesystem."""
    with open(local_path, 'r') as f:
        content = f.read()
    
    # Escape single quotes in content
    content_b64 = content
    
    print(f"[Upload] Uploading {local_path} -> /{remote_name} ({len(content)} bytes)")
    
    # Write file using MicroPython
    # Split into chunks to avoid buffer overflow
    chunk_size = 240
    chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
    
    # Open file for writing
    code = f"f = open('{remote_name}', 'w')\n"
    raw_repl_exec(ser, code)
    
    for i, chunk in enumerate(chunks):
        # Escape the chunk
        escaped = chunk.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')
        code = f"f.write('{escaped}')\n"
        result = raw_repl_exec(ser, code)
        if b'Error' in result or b'exception' in result:
            print(f"[ERROR] Chunk {i} failed: {result}")
        else:
            print(f"  Chunk {i+1}/{len(chunks)} OK")
    
    # Close file
    code = "f.close()\nprint('done')\n"
    result = raw_repl_exec(ser, code)
    print(f"[Upload] Done: {result}")
    return True

def verify_file(ser, remote_name):
    """Verify file was written correctly."""
    code = f"""
import os
stat = os.stat('{remote_name}')
print('size:', stat[6])
"""
    result = raw_repl_exec(ser, code)
    print(f"[Verify] {remote_name}: {result}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("=" * 50)
    print("Future Board AI - File Upload Tool")
    print("=" * 50)
    print(f"Port: {PORT}")
    
    ser = serial_connect()
    if not ser:
        print("[FAIL] Could not connect to Future Board")
        sys.exit(1)
    
    try:
        files = [
            ('micropython/ist8310.py', 'ist8310.py'),
            ('micropython/main.py', 'main.py'),
        ]
        
        for local_rel, remote in files:
            local_path = os.path.join(script_dir, local_rel)
            if os.path.exists(local_path):
                upload_file(ser, local_path, remote)
                verify_file(ser, remote)
            else:
                print(f"[SKIP] File not found: {local_path}")
        
        # List files on board
        print("\n[Files on board]")
        code = """
import os
files = os.listdir('/')
for f in files:
    stat = os.stat(f)
    print(f'  {f}: {stat[6]} bytes')
"""
        result = raw_repl_exec(ser, code)
        print(result.decode('utf-8', errors='replace'))
        
        # Soft reset to run main.py
        print("\n[Reset] Resetting board to run main.py...")
        ser.write(b'\x04')  # Ctrl+D = soft reset
        time.sleep(1)
        resp = ser.read_all()
        print(f"Boot output: {repr(resp[:200])}")
        
    finally:
        ser.close()
    
    print("\n[SUCCESS] Upload complete!")

if __name__ == '__main__':
    main()
