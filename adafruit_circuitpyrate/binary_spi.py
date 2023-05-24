import struct
import busio
import bitbangio
import digitalio

def run(serial_input, serial_output, pins):
    serial_output.write(b"SPI1")
    try:
        spi = busio.SPI(pins["clock"], pins["mosi"], pins["miso"])
    except ValueError:
        spi = bitbangio.SPI(pins["clock"], pins["mosi"], pins["miso"])
    cs = digitalio.DigitalInOut(pins["cs"])
    if not spi.try_lock():
        spi.deinit()
        return
    while True:
        command = serial_input.read(1)[0]
        if command == 0b00000000:
            spi.deinit()
            return
        elif command == 0b00000001:
            serial_output.write(b"SPI1")
        elif (command & 0x02) == 0x02:
            # Manual chip select
            cs.switch_to_output((command & 0x1) == 0x1)
        elif (command & 0b11111100) == 0x0c:
            # Skip the bus sniffing stuff
            pass
        elif (command & 0xf0) == 0x10:
            # Bulk read/write
            length = (command & 0xf) + 1
            out_data = serial_input.read(length)
            in_data = bytearray(length)
            spi.write_readinto(out_data, in_data)
            serial_output.write(in_data)
        elif command == 0x08 or command == 0x09:
            # Write then readinto.
            counts = serial_input.read(4)
            write_count, read_count = struct.unpack(">HH", counts)
            if write_count == 0 or read_count == 0:
                serial_output.write(b"\x00")
                continue
            try:
                write_buffer = serial_input.read(write_count)
                read_buffer = bytearray(read_count)
            except MemoryError:
                serial_output.write(b"\x00")
                continue
            if command == 0x08:
                cs.switch_to_output(False)
            spi.write(write_buffer)
            spi.readinto(read_buffer)
            if command == 0x08:
                cs.switch_to_output(True)
            serial_output.write(read_buffer)
