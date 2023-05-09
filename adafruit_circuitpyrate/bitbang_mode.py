# Documented here: http://dangerousprototypes.com/docs/Bitbang
import microcontroller

BINARY_MODES = ["spi", "i2c", "uart", "onewire", "rawwire", "openocd"]

def run(serial_input, serial_output, pins):
    while True:
        command = serial_input.read(1)[0]
        if command == 0b00000000:
            serial_output.write(b"BBIO1")
        elif command == 0b00001111:
            serial_output.write(b"\x01")
            return
        elif (command & 0xf0) == 0:
            number = (command & 0xf) - 1
            if number >= len(BINARY_MODES):
                # Invalid modes do nothing
                continue
            # Switch to mode
            mode_import_name = "binary_" + BINARY_MODES[number]
            full_import_name = "adafruit_circuitpyrate." + mode_import_name
            try:
                mode_module = __import__(full_import_name)
                # Get the package from the top level import.
                mode_module = getattr(mode_module, mode_import_name)
            except ImportError:
                print("Failed to import", full_import_name)
                continue
            mode_module.run(serial_input, serial_output, pins)
            # Back in bitbang mode so let the other side know.
            serial_output.write(b"BBIO1")
        elif (command & 0xe0) == 0b01000000:
            # Set pin direction
            pass
        elif (command & 0x80) != 0:
            # Set pin value
            pass
        serial_output.flush()
