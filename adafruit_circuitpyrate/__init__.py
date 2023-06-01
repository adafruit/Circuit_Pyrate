import analogio
import board
import digitalio
import os
import adafruit_prompt_toolkit as prompt_toolkit


# __version__ = "0.0.0+auto.0"
__version__ = "10.0.0"
# Our version must be > 2.4 for flashrom to work with the v2 api.
# TODO: Fix this URL
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_MCU_Flasher.git"

HELP_MENU = """
MENUS
?    \tHelp
= X  \tConverts X to dec/hex/bin
| X  \tReverse bits in byte X
i    \tVersion & status info
a/A/@\tAUXPIN (low/HIGH/READ)
d/D  \tMeasure ADC (once/CONT.)
g    \tFreq Generator/PWM on AUX
S    \tServo control on AUX

Unsupported: b, $"""

modes = (
    ("1-WIRE", "onewire"),
    ("UART", "uart"),
    ("I2C", "i2c"),
    ("SPI", "spi"),
    # ("2WIRE", "mode_2wire"),
    # ("3WIRE", "mode_3wire"),
    # ("KEYB", "keyb"),
    # ("LCD", "lcd"),
    # ("PIC", "pic"),
    # ("DIO", "dio")
)


class EnterBinaryMode(Exception):
    pass

class BinarySwitcher:
    def __init__(self, serial):
        self.serial = serial

    @property
    def in_waiting(self):
        return self.serial.in_waiting

    def read(self, length):
        buf = bytearray(length)
        read_count = 0
        null_count = 0
        while read_count < length:
            read = self.serial.read(1)
            if read[0] == 0:
                null_count += 1
                if null_count >= 20:
                    raise EnterBinaryMode()
                continue
            buf[read_count] = read[0]
            read_count += 1
        return buf

    def write(self, buffer):
        return self.serial.write(buffer)


class LEDToggler:
    def __init__(self, serial, *, tx_led, rx_led):
        self.serial = serial
        self.rx = rx_led
        self.rx.switch_to_output()
        self.tx = tx_led
        self.tx.switch_to_output()

    @property
    def in_waiting(self):
        return self.serial.in_waiting

    def read(self, length):
        result = self.serial.read(length)
        self.rx.value = True
        self.rx.value = False
        return result

    def write(self, buffer):
        self.tx.value = bool(buffer)
        result = self.serial.write(buffer)
        self.tx.value = False
        return result


class Mode:
    def __init__(self, input, output):
        self._input = input
        self._output = output
        self.macros = {}

        self.pull_ok = False

    def _print(self, *pos, end="\r\n"):
        pos = list(pos)
        for i, s in enumerate(pos):
            if isinstance(s, str):
                pos[i] = s.replace("\n", "\r\n")

        print(*pos, file=self._output, end=end)

    def _prompt(self, message) -> str:
        message = message.replace("\n", "\r\n")
        return prompt_toolkit.prompt(message, input=self._input, output=self._output)

    def _select_option(self, message, options, default=0):
        self._print(message)
        for i, option in enumerate(options):
            self._print(f" {i+1}. {option}")
        while True:
            selection = self._prompt(f"({default+1})>")
            if selection == "":
                return default
            try:
                selection = int(selection, 10) - 1
            except ValueError:
                selection = -1
            if 0 <= selection < len(options):
                return selection
            print("Invalid choice, try again")

    def run_macro(self, number):
        if number == 0:
            self._print("0. Macro menu")
            options = sorted(self.macros.keys())
            for num in options:
                name, _ = self.macros[num]
                self._print(f"{num}. {name}")
        else:
            if number not in self.macros:
                self._print("Unknown macro, try ? or (0) for help")
                return
            _, func = self.macros[number]
            func()


class HiZ(Mode):
    name = "HiZ"

    def deinit(self):
        pass

    def run_sequence(self, sequence):
        pass

    def print_pin_functions(self):
        self._print("CLK     MOSI    CS      MISO")

    def print_pin_directions(self):
        self._print("I       I       I       I")


class BusRead:
    def __init__(self, bits=8, repeat=1):
        self.bits = bits
        self.repeat = repeat

    def __repr__(self):
        return f"BusRead(repeat={self.repeat})"


class BusWrite:
    def __init__(self, value, bits=8, repeat=1):
        self.value = value
        self.bits = bits
        self.repeat = repeat

    def __repr__(self):
        return f"BusWrite(0x{self.value:x}, repeat={self.repeat})"


class BusClockTick:
    def __init__(self, repeat=1):
        self.repeat = repeat


class BusBitRead:
    def __init__(self, repeat=1):
        self.repeat = repeat


bus_sequence_chars = {
    "{": "START",
    "[": "START",
    "}": "STOP",
    "]": "STOP",
    "r": BusRead,
    "^": BusClockTick,
    "/": "CLOCK_HIGH",
    "\\": "CLOCK_LOW",
    "-": "DATA_HIGH",
    "_": "DATA_LOW",
    "!": BusBitRead,
    ".": "READ_PIN",
}


def _parse_action(unparsed):
    print(unparsed)
    if ";" in unparsed:
        # TODO: Partial
        pass
    elif ":" in unparsed:
        i = unparsed.index(":")
        repeat = int("".join(unparsed[i + 1 :]), 0)
        unparsed = unparsed[:i]
    else:
        repeat = 1

    if unparsed[0] in bus_sequence_chars:
        value = bus_sequence_chars[unparsed[0]]
        if isinstance(value, str):
            if repeat > 1:
                return None
            return value
        else:
            return value(repeat=repeat)
    try:
        write_value = int("".join(unparsed), 0)
        return BusWrite(value=write_value, repeat=repeat)
    except ValueError:
        return None
    return None


def parse_bus_actions(commands):
    bus_sequence = []
    unparsed = []
    numeric_ok = True
    for c in commands:
        numeric = c in "0123456789xabcdefABCDEF"
        if unparsed and (c in " ," or c in bus_sequence_chars or numeric != numeric_ok):
            action = _parse_action(unparsed)
            if action is None:
                return []
            bus_sequence.append(action)
            unparsed = []
            numeric_ok = True

        if c not in " ,":
            numeric_ok = numeric or c in ":;"
            unparsed.append(c)

    if unparsed:
        action = _parse_action(unparsed)
        if action is None:
            return []
        bus_sequence.append(action)
    return bus_sequence


class Pyrate:
    def __init__(
        self,
        input_,
        output,
        *,
        aux_pin,
        adc_pin,
        mosi_pin,
        clock_pin,
        miso_pin,
        cs_pin,
        enable_5v_pin,
        enable_3v_pin,
        enable_pullups_pin,
        measure_5v_pin,
        measure_3v_pin,
        vextern_pin,
        mode_led_pin,
        scl_pin=None,
        sda_pin=None
    ):
        self._input = input_
        self.output = output
        self.aux = digitalio.DigitalInOut(aux_pin)
        self.cs = None
        self.user_pin = self.aux

        self.power_5v = digitalio.DigitalInOut(enable_5v_pin)
        self.power_5v.switch_to_output(False)
        self.power_3v = digitalio.DigitalInOut(enable_3v_pin)
        self.power_3v.switch_to_output(False)

        self.mode_led = digitalio.DigitalInOut(mode_led_pin)
        self.mode_led.switch_to_output(False)

        self.enable_pullups = digitalio.DigitalInOut(enable_pullups_pin)
        self.enable_pullups.switch_to_output(False)

        # Bus pins
        self.pins = {}
        self.pins["mosi"] = mosi_pin
        self.pins["clock"] = clock_pin
        self.pins["miso"] = miso_pin
        self.pins["cs"] = cs_pin

        if scl_pin:
            self.pins["scl"] = scl_pin
        if sda_pin:
            self.pins["sda"] = sda_pin

        self.adc = analogio.AnalogIn(adc_pin)
        self.vextern = analogio.AnalogIn(vextern_pin)
        self.measure_3v = analogio.AnalogIn(measure_3v_pin)
        self.measure_5v = analogio.AnalogIn(measure_5v_pin)

        self.command_mapping = {
            "?": self.help_menu,
            "i": self.version_info,
            "b": self.change_baudrate,
            "=": self.convert_value,
            "|": self.reverse_value,
            "c": self.control_aux,
            "C": self.control_cs,
            "l": self.set_msb,
            "L": self.set_lsb,
            "a": self.set_pin_low,
            "A": self.set_pin_high,
            "@": self.read_pin,
            "d": self.read_one_voltage,
            "D": self.run_voltmeter,
            "g": self.frequency_generator,
            "S": self.servo_position,
            "m": self.change_mode,
            "w": self.power_off,
            "W": self.power_on,
            "v": self.print_pin_states,
            "p": self.disable_pulls,
            "P": self.enable_pulls,
        }

        self.history = []

        self.mode = None
        self.change_mode("1")

    def _print(self, *pos, end="\r\n"):
        pos = list(pos)
        for i, s in enumerate(pos):
            if isinstance(s, str):
                pos[i] = s.replace("\n", "\r\n")

        print(*pos, file=self.output, end=end)

    def _prompt(self, message) -> str:
        return prompt_toolkit.prompt(message, input=self._input, output=self.output)

    def help_menu(self, args):
        self._print(HELP_MENU)

    def version_info(self, args):
        self._print(f"Bus Pirate on {board.board_id}")
        self._print(f"Firmware v{__version__} on CircuitPython {os.uname().version}")
        self._print("https://adafruit.com")

    def change_baudrate(self, args):
        self._print("No baud rate change required for USB!")

    def _parse_int_value(self, string):
        string = string.lstrip()
        try:
            val = int(string, 0)
            return val
        except:
            print("Invalid input! " + string)
        return None

    def _print_value(self, val):
        self._print("0x{:02X} = {} = {:08b} ".format(val, val, val))

    def convert_value(self, args):
        val = self._parse_int_value(args)
        self._print_value(val)

    def reverse_value(self, args):
        val = self._parse_int_value(args)
        flipped = 0
        for i in range(8):
            flipped >>= 1
            if val & 0x80:
                flipped |= 0x80
            val <<= 1
        val = flipped & 0xFF
        self._print_value(flipped)

    def control_aux(self, args):
        if self.cs:
            self.cs.deinit()
            self.cs = None
        self.user_pin = self.aux

    def control_cs(self, args):
        # Use the mode's cs DigitalInOut when available.
        if hasattr(self.mode, "cs"):
            self.user_pin = self.mode.cs
        else:
            self.cs = digitalio.DigitalInOut(self.pins["cs"])
            self.user_pin = self.cs

    def set_msb(self, args):
        self.lsb = False

    def set_lsb(self, args):
        self.lsb = True

    def set_pin_low(self, args):
        self.user_pin.switch_to_output(value=False)
        self._print("AUX LOW")

    def set_pin_high(self, args):
        self.user_pin.switch_to_output(value=True)
        self._print("AUX HIGH")

    def read_pin(self, args):
        self.user_pin.switch_to_input()
        self._print("AUX INPUT/HI-Z, READ:", 1 if self.user_pin.value else 0)

    def _read_voltage(self, adc):
        return adc.value / 65535 * adc.reference_voltage * 2

    # Voltmeter readings
    def read_one_voltage(self, args):
        self._print("VOLTAGE PROBE %0.2fV" % self._read_voltage(self.adc))

    def run_voltmeter(self, args):
        self._print("VOLTMETER MODE\nAny key to exit")
        while self.serial.in_waiting == 0:
            self.read_one_voltage(None)
            time.sleep(0.1)
        # throw away the character
        self.serial.read(1)
        self._print("DONE")

    def power_on(self, args):
        self.power_3v.value = True
        self.power_5v.value = True
        self._print("Power supplies ON")

    def power_off(self, args):
        self.power_3v.value = False
        self.power_5v.value = False
        self._print("Power supplies OFF")

    def print_pin_states(self, args):
        self._print("Pinstates:")
        self._print(
            "1.(BR)  2.(RD)  3.(OR)  4.(YW)  5.(GN)  6.(BL)  7.(PU)  8.(GR)  9.(WT)  0.(Blk)"
        )
        self._print("GND     3.3V    5.0V    ADC     VPU     AUX     ", end="")
        self.mode.print_pin_functions()
        self._print("P       P       P       I       I       I       ", end="")
        self.mode.print_pin_directions()
        formatted_voltages = []
        for adc in (self.measure_3v, self.measure_5v, self.adc, self.vextern):
            formatted_voltages.append(f"{self._read_voltage(adc):1.2f}V   ")
        formatted_voltages = "".join(formatted_voltages)
        self._print(f"GND     {formatted_voltages}L       L       L       L       L")

    def enable_pulls(self, args):
        if not self.mode.pull_ok:
            self._print("Command not used in this mode")
            return
        self.enable_pullups.value = True
        self._print("Pull-up resistors ON")
        if self.vextern.value < 1000:
            self._print("Warning: no voltage on Vpullup pin")

    def disable_pulls(self, args):
        if not self.mode.pull_ok:
            self._print("Command not used in this mode")
            return
        self.enable_pullups.value = False
        self._print("Pull-up resistors OFF")

    def frequency_generator(self, args):
        # print("0.001 - 6000 KHz PWM/frequency generator")
        # print("(above 2 MHz frequency output is approximate)")

        # freq = input("Frequency in KHz: ")
        # try:
        #     freq = float(freq)
        #     if (freq < 0.001) or (freq > 6000000):
        #         raise exception()
        # except:
        #     print("Invalid input! "+str(freq))
        #     continue

        # duty = input("Duty Cycle in % ")
        # try:
        #     duty = float(duty)
        #     if (duty < 0) or (duty > 100):
        #         raise exception()
        # except:
        #     print("Invalid input! "+str(duty))
        #     continue
        # # convert to 16 bit
        # duty = int(65535 * duty / 100)
        # # convert to hz
        # freq = int( (freq * 1000) + 0.5) # help round imprecise floats

        # print("PWM Active: {:d} {:0.2f}%".format(freq, duty/655.35))
        # AUX.deinit()
        # AUX = pwmio.PWMOut(AUXPIN, duty_cycle=duty, frequency=freq)
        # AUX_PWMENABLED = True
        pass

    def servo_position(self, args):
        # print("Servo position in degrees (0-180) or uS (200 - 3000)")
        # servoval = 0

        # AUX.deinit()
        # AUX_PWMENABLED = True
        # AUX = pwmio.PWMOut(AUXPIN, frequency = 50)
        # while True:
        #     if (servoval < 200):
        #         suffix = "*"
        #     else:
        #         suffix = " uS"
        #     prompt = "(%d%s)>" % (servoval, suffix)
        #     val = input(prompt)

        #     if not val:
        #         break

        #     try:
        #         val = int(val)
        #         print(val)
        #         if (val >= 0) and (val <= 180):
        #             # degrees mode
        #             pulseWidth = 0.5 + (val / 180) * (SERVO_MAXPULSE - SERVO_MINPULSE)
        #         elif (val >= 200) or (val <= 3000):
        #             pulseWidth = val / 1000
        #         else:
        #             raise exception()
        #     except:
        #         print("Invalid input: "+str(val))
        #         continue
        #     dutyPercent = pulseWidth / 20.0
        #     AUX.duty_cycle = int(dutyPercent * 65535)
        #     servoval = val
        pass

    def change_mode(self, args):
        # print("mode", repr(args))
        if not args:
            self._print("1. HiZ")
            for i, mode in enumerate(modes):
                name, _ = mode
                self._print(f"{i+2}. {name}")
            selection = self._prompt("(1) > ")
        else:
            selection = args

        if self.mode:
            self.mode.deinit()
        self.mode = None

        try:
            new_mode = int(selection)
        except ValueError:
            new_mode = 1

        if new_mode == 1:
            self.mode = HiZ(self._input, self.output)
        else:
            _, mode_import_name = modes[new_mode - 2]
            full_import_name = "adafruit_circuitpyrate." + mode_import_name
            try:
                mode_module = __import__(full_import_name)
                # Get the package from the top level import.
                mode_module = getattr(mode_module, mode_import_name)
            except ImportError:
                print("Failed to import", mode_import_name)
                mode_module = None
            mode_class = None
            if mode_module:
                # Find the subclass of Mode
                for attr in dir(mode_module):
                    entry = getattr(mode_module, attr)
                    if isinstance(entry, type) and issubclass(entry, Mode):
                        mode_class = entry
                        break
            if mode_class is None:
                self._print("Unknown mode")
                self.mode = HiZ(self._input, self.output)
            else:
                try:
                    self.mode = mode_class(self.pins, self._input, self.output)
                    self._print("Mode selected")
                except BaseException as e:
                    if isinstance(e, ReloadException):
                        raise e
                    # Catch errors and go back to HiZ. Otherwise, we'll stop CircuitPython and be unresponsive.
                    print(repr(e))
                    self.mode = HiZ(self._input, self.output)
                    self._print("Mode failed")

        self.mode_led.value = not isinstance(self.mode, HiZ)

    def run_commands(self, commands):
        if not commands:
            return
        c = commands[0]
        args = commands[1:]

        if c in self.command_mapping:
            self.command_mapping[c](args)
        elif c == "h":
            for i, cmd in enumerate(reversed(self.history)):
                serial.write(f"{i+1}. {cmd}\r\n".encode("utf-8"))
            serial.write(b"x. exit\r\n(0) ")
            selection = serial.read(1)
            serial.write(selection)
            serial.write(b"\r\n")
            try:
                selection = int(selection)
            except ValueError:
                selection = 0
            if selection > 0:
                commands = history[-selection]
                self.run_commands(commands)
        elif c == "#" or c == "$":
            yn = self._prompt("Are you sure? ")
            print(repr(yn))
            if yn == "y":
                self.soft_reset()
        elif c == "(":
            m = int(commands.strip("()"), 0)
            self.mode.run_macro(m)
        else:
            # Assume bus sequence.
            bus_sequence = parse_bus_actions(commands)
            if bus_sequence:
                self.mode.run_sequence(bus_sequence)

    def soft_reset(self):
        if self.mode:
            self.mode.deinit()
        self.version_info(None)
        self.mode = HiZ(self._input, self.output)
        self.mode_led.value = False

    def run_binary_command(self, command) -> bool:
        if (command & 0xf0) == 0x40:
            enable_power = (command & 0x8) != 0
            self.power_3v.value = enable_power
            self.power_5v.value = enable_power
            enable_pulls = (command & 0x4) != 0
            self.enable_pullups.value = enable_pulls
            aux_high = (command & 0x2) != 0
            self.aux.switch_to_output(value=aux_high)
            cs_high = (command & 0x1) != 0
            self.cs.switch_to_output(value=cs_high)
            return True
        return False

    def run_binary_mode(self) -> bool:
        from . import bitbang_mode

        # We manage CS in bitbang mode.
        self.cs = digitalio.DigitalInOut(self.pins["cs"])
        # Don't pass the wrapped input because it'll raise more exceptions.
        bitbang_mode.run(self._input.serial, self.output, self)
        self.cs.deinit()
        self.cs = None
        self.soft_reset()
