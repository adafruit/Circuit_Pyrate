import struct
import busio
import bitbangio

def run(serial_input, serial_output, pins):
    serial_output.write(b"I2C1")
    try:
        i2c = busio.I2C(scl=pins["scl"], sda=pins["sda"])
    except ValueError:
        i2c = bitbangio.I2C(scl=pins["scl"], sda=pins["sda"])
    while True:
        command = serial_input.read(1)[0]
        if command == 0b00000000:
            i2c.deinit()
            return
        elif command == 0b00000001:
            serial_output.write(b"I2C1")
        elif command <= 0b00000111:
            # Skip the manual bit stuff
            pass
        elif command == 0x08:
            # Write then readinto.
            counts = serial_input.read(4)
            write_count, read_count = struct.unpack(">HH", counts)
            write_buffer = serial_input.read(write_count)
            read_buffer = bytearray(read_count)
            i2c_address = write_buffer[0] >> 1

            if not i2c.try_lock():
                continue
            if write_count > 1 and read_buffer:
                i2c.writeto_then_readfrom(i2c_address, write_buffer, read_buffer, out_start=1)
            elif write_count > 1:
                i2c.writeto(i2c_address, write_buffer, start=1)
            else:
                i2c.readfrom_into(i2c_address, read_buffer)
            serial_output.write(read_buffer)
            i2c.unlock()
