import analogio
import digitalio
import adafruit_prompt_toolkit as prompt_toolkit

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
    # ("1-WIRE", "onewire"),
    # ("UART", "uart"),
    ("I2C", "i2c"),
    # ("SPI", "spi"),
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
    def __init__(self, serial_input):
        self.serial_input = serial_input

    def read(self, length):
        buf = bytearray(length)
        read_count = 0
        null_count = 0
        while read_count < length:
            read = self.serial_input.read(1)
            if read[0] == 0:
                null_count += 1
                if null_count >= 20:
                    raise EnterBinaryMode()
                continue
            buf[read_count] = read[0]
            read_count += 1
        return buf


class Mode:
    def __init__(self, input, output):
        self._input = input
        self._output = output

    def _print(self, *pos, end="\r\n"):
        pos = list(pos)
        for i, s in enumerate(pos):
            if isinstance(s, str):
                pos[i] = s.replace("\n", "\r\n")

        print(*pos, file=self._output, end=end)

    def _prompt(self, message) -> str:
        message = message.replace("\n", "\r\n")
        return prompt_toolkit.prompt(message, input=self._input, output=self._output)

    def run_macro(self, number):
        if number == 0:
            self._print("0. Macro menu")
            for num in self.macros:
                name, _ = self.macros[num]
                self._print(f"{num}. {name}")
        else:
            _, func = self.macros[number]
            func()

class HiZ(Mode):
    name = "HiZ"

    def run_sequence(self, sequence):
        pass

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
    ".": "READ_PIN"
}

def _parse_action(unparsed):
    print(unparsed)
    if ";" in unparsed:
        # TODO: Partial
        pass
    elif ":" in unparsed:
        i = unparsed.index(":")
        repeat = int("".join(unparsed[i+1:]), 0)
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
    def __init__(self, input_, output, *, aux_pin, adc_pin, mosi_pin, clock_pin, miso_pin, cs_pin, scl_pin=None, sda_pin=None):
        self._input = input_
        self.output = output
        self.aux_pin = aux_pin
        self.user_pin = digitalio.DigitalInOut(aux_pin)

        # Bus pins
        self.pins = {}
        self.pins["cs"] = cs_pin
        self.pins["mosi"] = mosi_pin
        self.pins["clock"] = clock_pin
        self.pins["miso"] = miso_pin

        if scl_pin:
            self.pins["scl"] = scl_pin
        if sda_pin:
            self.pins["sda"] = sda_pin

        self.adc_pin = analogio.AnalogIn(adc_pin)

        self.command_mapping = {
            '?': self.help_menu,
            'i': self.version_info,
            'b': self.change_baudrate,
            '=': self.convert_value,
            '|': self.reverse_value,
            'c': self.control_aux,
            'C': self.control_cs,
            'l': self.set_msb,
            'L': self.set_lsb,
            'a': self.set_pin_low,
            'A': self.set_pin_high,
            '@': self.read_pin,
            'd': self.read_one_voltage,
            'D': self.run_voltmeter,
            'g': self.frequency_generator,
            'S': self.servo_position,
            'm': self.change_mode
        }

        self.history = []

        self.change_mode("1")

    def _print(self, *pos):
        pos = list(pos)
        for i, s in enumerate(pos):
            if isinstance(s, str):
                pos[i] = s.replace("\n", "\r\n")

        print(*pos, file=self.output, end="\r\n")

    def _prompt(self, message) -> str:
        return prompt_toolkit.prompt(message, input=self._input, output=self.output)

    def help_menu(self, args):
        self._print(HELP_MENU)

    def version_info(self, args):
        import os
        self._print("Circuit Pyrate v0\nwww.adafruit.com")
        self._print("Hardware: "+os.uname().machine)
        self._print("CircuitPython: "+os.uname().version)

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
        self._print('0x{:02X} = {} = {:08b} '.format(val, val, val))

    def convert_value(self, args):
        val = self._parse_int_value(args)
        self._print_value(val)

    def reverse_value(self, args):
        val = self._parse_int_value(args)
        flipped = 0
        for i in range(8):
            flipped >>= 1
            if (val & 0x80):
                flipped |= 0x80
            val <<= 1
        val = flipped & 0xFF
        self._print_value(flipped)

    def control_aux(self, args):
        self.user_pin.deinit()
        self.user_pin = digitalio.DigitalInOut(self.aux_pin)

    def control_cs(self, args):
        self.user_pin.deinit()
        self.user_pin = digitalio.DigitalInOut(self.cs_pin)

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

    # Voltmeter readings
    def read_one_voltage(self, args):
        self._print("VOLTAGE PROBE %0.2fV" %
              (self.adc_pin.value / 65535 * self.adc_pin.reference_voltage))
    
    def run_voltmeter(self, args):
        self._print("VOLTMETER MODE\nAny key to exit")
        while self.serial.in_waiting == 0:
            self.read_one_voltage(None)
            time.sleep(0.1)
        # throw away the character
        self.serial.read(1)
        self._print("DONE")

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
        print("mode", repr(args))
        if not args:
            self._print("1. HiZ")
            for i, mode in enumerate(modes):
                name, _ = mode
                self._print(f"{i+2}. {name}")
            selection = self._prompt("(1) > ")
        else:
            selection = args

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
                    print("attr", attr, entry)
                    if isinstance(entry, type) and issubclass(entry, Mode):
                        mode_class = entry
                        break
            if mode_class is None:
                self._print("Unknown mode")
                self.mode = HiZ(self._input, self.output)
            else:
                self._print("Mode selected")
                self.mode = mode_class(self.pins, self._input, self.output)

    def run_commands(self, commands):
        if not commands:
            return
        c = commands[0]
        args = commands[1:]

        if c in self.command_mapping:
            self.command_mapping[c](args)
        elif c == 'h':
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
            serial.write("Are you sure? ")
            yn = serial.read(1)
            serial.write(yn)
            serial.write(b"\r\n")
            if yn == b"y":
                # TODO: We probably shouldn't reset completely because the bus pirate
                # wouldn't reset USB because it is a USB to serial converter.
                if c == "$":
                    microcontroller.on_next_reset(microcontroller.RunMode.BOOTLOADER)
                    serial.write(b"BOOTLOADER\r\n")
                else:
                    serial.write(b"RESET\r\n")
                microcontroller.reset()
        elif c == "(":
            m = int(commands.strip("()"), 0)
            self.mode.run_macro(m)
        else:
            # Assume bus sequence.
            bus_sequence = parse_bus_actions(commands)
            if bus_sequence:
                self.mode.run_sequence(bus_sequence)

    def run_binary_mode(self):
        from . import bitbang_mode
        # Don't pass the wrapped input because it'll raise more exceptions.
        bitbang_mode.run(self._input.serial_input, self.output, self.pins)
