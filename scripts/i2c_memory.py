import adafruit_board_toolkit.circuitpython_serial
import serial
import struct
import time
import datetime

comports = adafruit_board_toolkit.circuitpython_serial.data_comports()
if not comports:
    raise Exception("No CircuitPython boards found")


# Enter raw mode
print(comports[0])

serial = serial.Serial(comports[0].device)

def write_then_readinto(serial, out_buffer, in_buffer):
    serial.write(b"\x08")
    serial.write(struct.pack(">HH", len(out_buffer), len(in_buffer)))
    serial.write(out_buffer)
    if in_buffer:
        serial.readinto(in_buffer)

for i in range(21):
    serial.write(b"\x00")
    time.sleep(0.1)
    if serial.in_waiting >= 5:
        response = serial.read(5)
        assert response == b"BBIO1"
        serial.reset_input_buffer()
        break

# Switch to I2C mode
serial.write(b"\x02")
response = serial.read(4)
assert b"I2C1" == response

in_buffer = bytearray(32)
write_then_readinto(serial, b"\xa0\x00\x00", in_buffer)

print("first read:", in_buffer)
data = "hello pyrate " + str(datetime.datetime.now())
# truncate to 32 byte page boundary to prevent overwriting hello
data = data[:32]
out = b"\xa0\x00\x00" + data.encode("utf-8")
print("writing", out)
write_then_readinto(serial, out, b"")
