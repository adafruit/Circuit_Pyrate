import struct
import busio
import bitbangio
import digitalio

SPEEDS_KHZ = [30, 125, 250, 1000, 2600, 4000, 8000]

def run(serial_input, serial_output, pyrate):
    serial_output.write(b"SPI1")
    pins = pyrate.pins
    try:
        spi = busio.SPI(pins["clock"], pins["mosi"], pins["miso"])
    except ValueError:
        spi = bitbangio.SPI(pins["clock"], pins["mosi"], pins["miso"])

    if not spi.try_lock():
        spi.deinit()
        return

    current_config = {
        "baudrate": SPEEDS_KHZ[0] * 1000,
        "polarity": 0,
        "phase": 0
    }

    spi.configure(**current_config)
    while True:
        command = serial_input.read(1)[0]
        if command == 0b00000000:
            spi.deinit()
            return
        elif command == 0b00000001:
            serial_output.write(b"SPI1")
        elif (command & 0xfe) == 0x02:
            # Manual chip select
            pyrate.cs.switch_to_output((command & 0x1) == 0x1)
            serial_output.write(b"\x01")
        elif (command & 0b11111100) == 0x0c:
            # Skip the bus sniffing stuff
            pass
        elif (command & 0xf8) == 0x60:
            # Set speed
            i = command & 0x7
            current_config["baudrate"] = SPEEDS_KHZ[i] * 1000
            spi.configure(**current_config)
            serial_output.write(b"\x01")
        elif (command & 0xf0) == 0x80:
            # Check that it is 3.3v high and sample in middle.
            if (command & 0x9) != 0b1000:
                serial_output.write(b"\x00")
            current_config["polarity"] = (command >> 2) & 0x1
            current_config["phase"] = (command >> 1) & 0x1
            spi.configure(**current_config)
            serial_output.write(b"\x01")
        elif (command & 0xf0) == 0x10:
            # Bulk read/write
            length = (command & 0xf) + 1
            out_data = serial_input.read(length)
            in_data = bytearray(length)
            spi.write_readinto(out_data, in_data)
            serial_output.write(in_data)
        elif command == 0x04 or command == 0x05:
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
            if command == 0x04:
                pyrate.cs.switch_to_output(False)
            spi.write(write_buffer)
            spi.readinto(read_buffer)
            if command == 0x04:
                pyrate.cs.switch_to_output(True)
            serial_output.write(b"\x01")
            serial_output.write(read_buffer)
        elif pyrate.run_binary_command(command):
            serial_output.write(b"\x01")
            # Handled by the shared commands.
            pass
        else:
            print("unhandled SPI command", hex(command))
