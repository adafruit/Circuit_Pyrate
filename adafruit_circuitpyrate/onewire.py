from adafruit_circuitpyrate import Mode, BusWrite, BusRead
import adafruit_prompt_toolkit as prompt_toolkit

import array
import adafruit_onewire.bus
 
KNOWN_DEVICES = {
    0x10: "DS18S20 High Prec Dig Therm",
    0x28: "DS18B20 Prog Res Dig Therm",
    0x22: "DS1822 Econo Dig Therm",
    0x04: "DS2404 EconoRAM time Chip",
    0x2D: "DS2431 1K EEPROM"
}

class OneWire(Mode):
    name = "1-WIRE"

    def __init__(self, pins, input, output):
        super().__init__(input, output)

        self.onewire = adafruit_onewire.bus.OneWireBus(pins["mosi"])

        self.macros = {
            51 : ("READ ROM (0x33) *for single device bus", self.read_rom),
            # 85 : ("MATCH ROM (0x55) *followed by 64bit address", self.match_rom),
            204: ("SKIP ROM (0xCC) *followed by command", self.skip_rom),
            # 236: ("ALARM SEARCH (0xEC)", self.alarm_search),
            240: ("SEARCH ROM (0xF0)", self.search_rom),
        }

        self.pull_ok = True

    def deinit(self):
        self.onewire.deinit()

    def print_pin_functions(self):
        self._print("-       OWD     -       -")

    def print_pin_directions(self):
        self._print("I       I       I       I")

    def read_rom(self):
        self.onewire.reset()
        self._print("BUS RESET  OK")
        self.onewire.write(b"\x33")
        buf = bytearray(8)
        self.onewire.readinto(buf)
        self._print("READ ROM (0x33):", end="")
        for b in buf:
            self._print(f" 0x{b:02X}", end="")
        self._print()
        if buf[0] in KNOWN_DEVICES:
            self._print(KNOWN_DEVICES[buf[0]])
        else:
            self._print("Unknown device")

    def skip_rom(self):
        pass

    def search_rom(self):
        self._print("Macro    1WIRE address")
        for i, device in enumerate(self.onewire.scan()):
            self._print(f" {i}.", end="")
            for b in device.rom:
                self._print(f" 0x{b:02X}", end="")
            self._print()
            if device.rom[0] in KNOWN_DEVICES:
                self._print(KNOWN_DEVICES[device.rom[0]])
            else:
                self._print("Unknown device")

    def run_sequence(self, sequence):
        for action in sequence:
            if action == "START":
                self.onewire.reset()
                self._print("BUS RESET  OK")
            elif isinstance(action, BusWrite):
                buf = bytearray(action.repeat)
                self._print(f"WRITE:", end="")
                for i in range(action.repeat):
                    buf[i] = action.value
                    self._print(f" 0x{buf[i]:02X}", end="")
                self._print()
                self.onewire.write(buf)
            elif isinstance(action, BusRead):
                buf = bytearray(action.repeat)
                self._print("READ:", end="")
                self.onewire.readinto(buf)
                for i in range(action.repeat):
                    self._print(f" 0x{buf[i]:02X}", end="")
                self._print()
