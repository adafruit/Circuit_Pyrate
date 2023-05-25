from adafruit_circuitpyrate import Mode, BusWrite, BusRead
import adafruit_prompt_toolkit as prompt_toolkit

import array
import busio
import bitbangio
import digitalio
 
SPEEDS = (30, 125, 250, 1000)

class SPI(Mode):
    name = "SPI"

    def __init__(self, pins, input, output):
        super().__init__(input, output)

        speed = self._select_option("Set speed:", ["30KHz", "125KHz", "250KHz", "1MHz"])
        self.speed = SPEEDS[speed] * 1000

        self.polarity = self._select_option("Clock polarity:", ["Idle low *default", "Idle high"])
        self.phase = self._select_option("Output clock edge:", ["Idle to active", "Active to idle *default"], default=1)
        # No support for input sample phase.
        self.cs_idle = self._select_option("CS:", ["CS", "/CS *default"], default=1) == 1
        # No support for open drain SPI.

        try:
            print("native SPI")
            self.spi = busio.SPI(pins["clock"], pins["mosi"], pins["miso"])
        except ValueError as e:
            print("bitbang SPI", repr(e))
            self.spi = bitbangio.SPI(pins["clock"], pins["mosi"], pins["miso"])

        self.cs = digitalio.DigitalInOut(pins["cs"])
        self.cs.switch_to_output(self.cs_idle)

        self.macros = {
            # No CP API. 1: ("Sniff CS low", self.sniff)
            # No CP API. 2: ("Sniff all traffic", self.sniff)
        }

        self.pull_ok = True

    def deinit(self):
        self.spi.deinit()
        self.cs.deinit()

    def print_pin_functions(self):
        self._print("CLK     MOSI    CS      MISO")

    def print_pin_directions(self):
        self._print("O       O       O       I")

    def run_sequence(self, sequence):
        if not self.spi.try_lock():
            return

        self.spi.configure(baudrate=self.speed, polarity=self.polarity, phase=self.phase, bits=8)

        for action in sequence:
            if action == "START":
                self.cs.value = not self.cs_idle
                if self.cs_idle:
                    self._print("/", end="")
                self._print("CS ENABLED")
            elif action == "STOP":
                self.cs.value = self.cs_idle
                if self.cs_idle:
                    self._print("/", end="")
                self._print("CS DISABLED")
            elif isinstance(action, BusWrite):
                buf = bytearray(action.repeat)
                self._print(f"WRITE", end="")
                for i in range(action.repeat):
                    buf[i] = action.value
                    self._print(f" 0x{buf[i]:02X}", end="")
                self._print()
                self.spi.write(buf)
            elif isinstance(action, BusRead):
                buf = bytearray(action.repeat)
                self._print("READ", end="")
                self.spi.readinto(buf)
                for i in range(action.repeat):
                    self._print(f" 0x{buf[i]:02X}", end="")
                self._print()

        self.spi.unlock()