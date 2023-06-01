from adafruit_circuitpyrate import Mode, BusWrite, BusRead
import adafruit_prompt_toolkit as prompt_toolkit

import array
import busio
import digitalio
 
SPEEDS = (300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 31250)

class UART(Mode):
    name = "UART"

    def __init__(self, pins, input, output):
        super().__init__(input, output)

        # Determine if we can use busio.UART or have to use pio.
        try:
            native = busio.UART(tx=pins["mosi"], rx=pins["miso"])
            native.deinit()
            self.impl = busio.UART
        except ValueError as e:
            import adafruit_pio_uart
            self.impl = adafruit_pio_uart.UART

        speed = self._select_option("Set serial port speed: (bps)", [str(x) for x in SPEEDS])

        bits_parity = self._select_option("Data bits and parity:", ["8, NONE *default", "8, EVEN", "8, ODD", "9, NONE"])
        bits = 9 if bits_parity == 3 else 8
        parity = None
        if bits_parity == 1:
            parity = busio.UART.Parity.EVEN
        elif bits_parity == 2:
            parity = busio.UART.Parity.ODD
        stop_bits = self._select_option("Stop bits:", ["1 *default", "2"])
        # No support for receive polarity
        # No support for open drain UART

        self.kwargs = {
            "tx": pins["mosi"],
            "rx": pins["miso"],
            "parity": parity,
            "stop": stop_bits + 1,
            "baudrate": SPEEDS[speed],
            "timeout": 1
        }

        self.uart = self.impl(**self.kwargs)

        self.macros = {
            1: ("Transparent bridge", self.bridge),
            2: ("Live monitor", self.monitor),
            3: ("Bridge with flow control", self.bridge),
            # 4: ("Auto Baud Detection (Activity Needed)", self.detect_baudrate)
            5: ("Live monitor both RX and TX", self.dual_monitor),
        }

        self.pull_ok = True

    def deinit(self):
        self.uart.deinit()

    def print_pin_functions(self):
        self._print("-       TxD     -       RxD")

    def print_pin_directions(self):
        self._print("I       O       I       I")

    def dual_monitor(self):
        self._print("Dual UART input. May be reordered between TX and RX within groups.")
        self._print("Any key to exit")
        self.uart.deinit()
        tx = self.impl(rx=self.kwargs["tx"], parity=self.kwargs["parity"], stop=self.kwargs["stop"], baudrate=self.kwargs["baudrate"])
        rx = self.impl(rx=self.kwargs["rx"], parity=self.kwargs["parity"], stop=self.kwargs["stop"], baudrate=self.kwargs["baudrate"])
        both = (("TX", tx), ("RX", rx))
        buf = bytearray(32)
        mv = memoryview(buf)
        waiting_last = 0
        while not self._input.in_waiting:
            total_waiting = 0
            for name, serial in both:
                waiting = min(len(mv), serial.in_waiting)
                if waiting == 0:
                    continue
                total_waiting += waiting
                serial.readinto(mv[:waiting])
                self._print(name, end="")
                for i in range(waiting):
                    self._print(f" 0x{buf[i]:02X}", end="")
                self._print()
            if total_waiting == 0 and waiting_last > 0:
                self._print()
            waiting_last = total_waiting

        tx.deinit()
        rx.deinit()

        # Recreate the uart class
        self.uart = self.impl(**self.kwargs)


    def monitor(self):
        self._print("Raw UART input")
        self._print("Any key to exit")
        while not self._input.in_waiting:
            if self.uart.in_waiting:
                self._output.write(self.uart.read(self.uart.in_waiting))

    def bridge(self):
        self._print("UART bridge")
        self._print("Reset to exit")
        yn = self._prompt("Are you sure? ")
        if yn != "y":
            return
        while True:
            if self._input.in_waiting:
                self.uart.write(self._input.read(self._input.in_waiting))
            if self.uart.in_waiting:
                self._output.write(self.uart.read(self.uart.in_waiting))

    def run_sequence(self, sequence):

        for action in sequence:
            if action == "START":
                self.uart.reset_input_buffer()
            elif action == "STOP":
                pass
            elif isinstance(action, BusWrite):
                buf = bytearray(action.repeat)
                self._print(f"WRITE", end="")
                for i in range(action.repeat):
                    buf[i] = action.value
                    self._print(f" 0x{buf[i]:02X}", end="")
                self._print()
                self.uart.write(buf)
            elif isinstance(action, BusRead):
                buf = bytearray(action.repeat)
                n = self.uart.readinto(buf)
                if not n:
                    continue
                self._print("READ", end="")
                for i in range(n):
                    self._print(f" 0x{buf[i]:02X}", end="")
                self._print()
