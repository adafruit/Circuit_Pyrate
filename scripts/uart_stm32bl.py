import adafruit_board_toolkit.circuitpython_serial
import serial
import struct
import sys
import time
import datetime

if len(sys.argv) == 1:
    comports = adafruit_board_toolkit.circuitpython_serial.data_comports()
    if not comports:
        raise Exception("No CircuitPython boards found")

    device = comports[0].device
else:
    device = sys.argv[-1]


print("Connecting to", device)
serial = serial.Serial(device)

# Enter raw mode
for i in range(21):
    serial.write(b"\x00")
    time.sleep(0.1)
    if serial.in_waiting >= 5:
        response = serial.read(5)
        assert response == b"BBIO1"
        serial.reset_input_buffer()
        break

# Switch to UART mode
serial.write(b"\x03")
response = serial.read(4)
assert b"ART1" == response

# Setup 8E1 mode and set speed to 9600
serial.write(b"\x94")
assert serial.read(1) == b"\x01"

serial.write(b"\x64")
assert serial.read(1) == b"\x01"

# Toggle power to the device
serial.write(b"\x40")
assert serial.read(1) == b"\x01"

serial.write(b"\x48")
assert serial.read(1) == b"\x01"

time.sleep(0.1)

# Enable RX echo
serial.write(b"\x02")
assert serial.read(1) == b"\x01"

# Send the init code to the bootloader
serial.write(b"\x10\x7f")
assert serial.read(2) == b"\x01\x79"

# Read the chip id
serial.write(b"\x11\x02\xfd")
assert serial.read(2) == b"\x01\x01"

pid = serial.read(5)[2:4]
pid = struct.unpack(">H", pid)[0]
print("Chip id:", hex(pid))
