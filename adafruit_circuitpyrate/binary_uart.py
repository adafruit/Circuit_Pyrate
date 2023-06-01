import struct
import busio
import digitalio

SPEEDS = (300, 1200, 2400, 4800, 9600, 19200, 31250, 38400, 57600, 115200)

def run(serial_input, serial_output, pyrate):
    serial_output.write(b"ART1")
    # Determine if we can use busio.UART or have to use pio.
    try:
        native = busio.UART(tx=pyrate.pins["mosi"], rx=pyrate.pins["miso"])
        native.deinit()
        impl = busio.UART
    except ValueError as e:
        import adafruit_pio_uart
        impl = adafruit_pio_uart.UART

    kwargs = {
        "tx": pyrate.pins["mosi"],
        "rx": pyrate.pins["miso"],
        "parity": None,
        "stop": 1,
        "baudrate": 300,
        "timeout": 0
    }

    uart = impl(**kwargs)
    echo_rx = False
    while True:
        if echo_rx and uart.in_waiting > 0:
            buf = uart.read(uart.in_waiting)
            serial_output.write(buf)

        if serial_input.in_waiting == 0:
            continue
        command = serial_input.read(1)[0]
        if command == 0b00000000:
            uart.deinit()
            return
        elif command == 0b00000001:
            serial_output.write(b"ART1")
        elif (command & 0xfe) == 0x02:
            # Enable/disable echo RX bytes
            if (command & 0x1) == 1:
                echo_rx = False
            else:
                echo_rx = True
                uart.reset_input_buffer()
            serial_output.write(b"\x01")
        elif command == 0x07:
            # Skip the manual baudrate setting
            serial_output.write(b"\x00")
        elif command == 0x0f:
            # Bridge mode
            while True:
                if serial_input.in_waiting:
                    uart.write(serial_input.read(serial_input.in_waiting))
                if uart.in_waiting:
                    serial_output.write(uart.read(uart.in_waiting))

        elif (command & 0xf0) == 0x10:
            # Bulk write
            length = (command & 0xf) + 1
            for _ in range(length):
                out_data = serial_input.read(1)
                uart.write(out_data)
                serial_output.write(b"\x01")
        elif (command & 0xf0) == 0x60:
            # Set UART speed
            index = (command & 0xf)
            if index < 0 or index >= len(SPEEDS):
                serial_output.write(b"\x00")
                continue
            kwargs["baudrate"] = SPEEDS[index]
            uart.deinit()
            uart = impl(**kwargs)
            serial_output.write(b"\x01")
        elif (command & 0xe0) == 0x80:
            # Configure uart settings
            if (command & 0x10) == 0 or (command & 0x1) != 0: # Unsupported HiZ + idle low
                serial_output.write(b"\x00")
                continue
            bits_parity = (command >> 2) & 0x3
            bits = 9 if bits_parity == 3 else 8
            parity = None
            if bits_parity == 1:
                parity = busio.UART.Parity.EVEN
            elif bits_parity == 2:
                parity = busio.UART.Parity.ODD
            kwargs["parity"] = parity
            kwargs["bits"] = bits
            stop_bits = ((command >> 1) & 0x1) + 1
            kwargs["stop"] = stop_bits
            uart.deinit()
            uart = impl(**kwargs)
            serial_output.write(b"\x01")
        elif pyrate.run_binary_command(command):
            serial_output.write(b"\x01")
            # Handled by the shared commands.
            pass
        else:
            print("unhandled UART command", hex(command))
