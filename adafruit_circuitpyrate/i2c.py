from adafruit_circuitpyrate import Mode, BusWrite, BusRead
import adafruit_prompt_toolkit as prompt_toolkit

import array
import busio
import bitbangio
 
SPEEDS = (5, 50, 100, 400)

class I2C(Mode):
    name = "I2C"

    def __init__(self, pins, input, output):
        super().__init__(input, output)

        scl = pins["clock"]
        sda = pins["mosi"]
        if "scl" in pins:
            implementation = self._select_option("I2C pinout:", (f"{pins["clock"]}/{pins["mosi"]}", f"{pins["scl"]}/{pins["sda"]}"))
            if implementation == 1:
                scl = pins["scl"]
                sda = pins["sda"]

        speed = self._select_option("Set speed:", ["~5KHz", "~50KHz", "~100KHz", "~400KHz"])

        speed = SPEEDS[speed] * 1000

        hardware_possible = False
        try:
            print("native I2C")
            self.i2c = busio.I2C(scl=scl, sda=sda, frequency=speed)
            hardware_possible = True
        except ValueError as e:
            print("bitbang I2C", repr(e))
            self.i2c = bitbangio.I2C(scl=scl, sda=sda, frequency=speed)
        if hardware_possible:
            implementation = self._select_option("I2C mode:", ("Software", "Hardware"))
            # Switch to bitbang
            if implementation == 0:
                self.i2c.deinit()
                self.i2c = bitbangio.I2C(scl=scl, sda=sda, frequency=speed)


        self.macros = {
            1: ("7bit address search", self.scan),
            # No CP API. 2: ("I2C sniffer", self.sniff)
        }

        self.pull_ok = True

    def deinit(self):
        self.i2c.deinit()

    def print_pin_functions(self):
        self._print("SCL     SDA     -       -")

    def scan(self):
        if not self.i2c.try_lock():
            return
        self._print("Searching I2C address space. Found devices at:")
        addresses = self.i2c.scan()
        space = ""
        for address in addresses:
            self._print(f"{space}0x{address*2:02X}(0x{address:02X} W)")
            space = " "
        self.i2c.unlock()

    def run_sequence(self, sequence):
        next_start = 0
        while next_start < len(sequence) and sequence[next_start] == "START":
            start = next_start
            try:
                stop = sequence.index("STOP", start)
            except ValueError:
                print("Missing stop")
                break
            next_start = stop + 1

            try:
                repeated_start = sequence.index("START", start + 1)
            except ValueError:
                repeated_start = stop

            # Ignore starts after the next stop.
            if repeated_start > stop:
                repeated_start = stop

            first_address = sequence[start + 1]
            if not isinstance(first_address, BusWrite) and first_address.repeat == 1:
                print("Address not single byte write")
                continue

            # Prep write buffer because it is always first when present
            write_buffer = None
            if (first_address.value & 0x1) == 0x0:
                write_buffer = array.array("B")
                for action in sequence[start + 2: repeated_start]:
                    print("queue write", action)
                    if not isinstance(action, BusWrite):
                        continue
                    for _ in range(action.repeat):
                        write_buffer.append(action.value)
                read_start = stop
            else:
                read_start = start + 2


            if repeated_start < stop:
                if (first_address.value & 0x1) == 0x1:
                    print("first address must be write with repeated start")
                    continue

                second_address = sequence[repeated_start + 1]
                if not isinstance(second_address, BusWrite) or second_address.repeat > 1 or (second_address.value & 0x1) == 0x0:
                    print("second address must be write with lsb 0 and repeat 1")
                    continue
                second_address = second_address.value >> 1
                # Make sure addresses match
                if second_address != first_address.value >> 1:
                    print("Addresses don't match")
                    continue

                device_address = second_address
                read_start = repeated_start + 2
            else:
                device_address = first_address.value >> 1

            read_length = 0
            for action in sequence[read_start:stop]:
                if not isinstance(action, BusRead):
                    continue
                read_length += action.repeat
            read_buffer = bytearray(read_length)

            if not self.i2c.try_lock():
                return

            self._print("I2C START BIT")
            device_found = True
            if write_buffer and read_buffer:
                try:
                    self.i2c.writeto_then_readfrom(device_address, write_buffer, read_buffer)
                except OSError:
                    device_found = False
            elif write_buffer:
                try:
                    self.i2c.writeto(device_address, write_buffer)
                except OSError:
                    device_found = False
            else:
                try:
                    self.i2c.readinto(device_address, read_buffer)
                except OSError:
                    device_found = False

            if not device_found:
                self._print(f"WRITE 0x{sequence[start+1].value:02X} NACK")
                self._print("I2C STOP BIT")
                self.i2c.unlock()
                continue

            i = 0
            for action in sequence[start + 2: repeated_start]:
                if action.repeat > 1:
                    self._print("WRITE 0x{action.repeat:02X} BYTES:")
                    for j in range(action.repeat):
                        if j > 0:
                            self._print(" ", end="")
                        self._print(f"0x{write_buffer[i]:02X} ACK", end="")
                        i += 1
                        if not device_found:
                            break
                else:
                    self._print(f"WRITE 0x{write_buffer[i]:02X} ACK")
                    i += 1

                if not device_found:
                    break

            if write_buffer and read_buffer:
                self._print("I2C START BIT")
                self._print(f"WRITE 0x{sequence[repeated_start+1].value:02X} ACK")

            for action in sequence[repeated_start+2:stop]:
                i = 0
                if action.repeat > 1:
                    self._print(f"READ 0x{action.repeat:02X} BYTES:")
                    for j in range(action.repeat):
                        if j > 0:
                            self._print(" ", end="")
                        self._print(f"0x{read_buffer[i]:02X} ACK", end="")
                        i += 1
                        if not device_found:
                            break
                    self._print()
                else:
                    self._print(f"READ 0x{read_buffer[i]:02X} ACK")
                    i += 1

            self._print("I2C STOP BIT")

            self.i2c.unlock()
