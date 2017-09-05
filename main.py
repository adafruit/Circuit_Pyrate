import board
import time
from digitalio import DigitalInOut, Direction
from analogio import AnalogIn
import pulseio

# enums
MODE_HIZ = 0

# start in HiZ mode
MODE = MODE_HIZ

AUXPIN = board.D5
AUX = DigitalInOut(AUXPIN)
AUX_PWMENABLED = False

ADCPIN = AnalogIn(board.A0)

# make a mini REPL

HELP_MENU = """\
MENUS
?    \tHelp
= X  \tConverts X to dec/hex/bin
i    \tVersion & status info
a/A/@\tAUXPIN (low/HIGH/READ)
d/D  \tMeasure ADC (once/CONT.)
g    \tFreq Generator/PWM on AUX

Unsupported: b, $"""

VERSION_INFO = """\
Circuit Pyrate v0
www.adafruit.com"""

while True:
    prompt = ""
    if MODE == MODE_HIZ:
        prompt = "HiZ> "
    commands = input(prompt)
    if (not commands):
        continue
    
    print("->"+commands)

    c = commands[0]
    commands = commands[1:]
    if c == '?':
        print(HELP_MENU)
    elif c== 'i':
        import uos
        print(VERSION_INFO)
        print("Hardware: "+uos.uname().machine)
        print("CircuitPython: "+uos.uname().version)
    # Unsupported things
    elif c == 'b':
        print("No baud rate change required for USB!")
    elif c == '$':
        print("Double-click RESET to bootload!")
    # Conversion
    elif c == '=':
        arg = commands.lstrip()
        try:
            if (arg.startswith("0x")):
                val = int(arg, 16)
            elif (arg.startswith("0b")):
                val = int(arg, 2)
            elif (arg.startswith("0")):
                val = int(arg, 8)
            else:
                val = int(arg)
        except:
            print("Invalid input! "+arg)
            continue
        
        print('0x{:02X} = {} = {:08b} '.format(val, val, val))
    # AUXPIN
    elif c == 'a':
        print("AUX LOW")
        AUX.deinit()
        AUX = DigitalInOut(AUXPIN)
        AUX.direction = Direction.OUTPUT
        AUX.value = False
    elif c == 'A':
        print("AUX HIGH")
        AUX.deinit()
        AUX = DigitalInOut(AUXPIN)
        AUX.direction = Direction.OUTPUT
        AUX.value = True
    elif c == '@':
        AUX.deinit()
        AUX = DigitalInOut(AUXPIN)
        AUX.direction = Direction.INPUT
        print("AUX INPUT, READ: %d" % AUX.value)

    # PWM output on AUX
    elif c == 'g' and not AUX_PWMENABLED:
        print("0.001 - 6000 KHz PWM/frequency generator")
        print("(above 2 MHz frequency output is approximate)")

        freq = input("Frequency in KHz: ")
        try:
            freq = float(freq)
            if (freq < 0.001) or (freq > 6000000):
                raise exception()
        except:
            print("Invalid input! "+str(freq))
            continue

        duty = input("Duty Cycle in % ")
        try:
            duty = float(duty)
            if (duty < 0) or (duty > 100):
                raise exception()
        except:
            print("Invalid input! "+str(duty))
            continue
        # convert to 16 bit
        duty = int(65535 * duty / 100)
        # convert to hz
        freq = int( (freq * 1000) + 0.5) # help round imprecise floats
        
        print("PWM Active: {:d} {:0.2f}%".format(freq, duty/655.35)) 
        AUX.deinit()
        AUX = pulseio.PWMOut(AUXPIN, duty_cycle=duty, frequency=freq)
        AUX_PWMENABLED = True

    elif c == 'g' and AUX_PWMENABLED:
        AUX.deinit()
        AUX = DigitalInOut(AUXPIN)
        AUX.direction = Direction.INPUT
        AUX_PWMENABLED = False
        print("PWM disabled")

    # Voltmeter readings
    elif c == 'd':
        print("VOLTAGE PROBE %0.2fV" %
              (ADCPIN.value / 65535 * ADCPIN.reference_voltage))
    elif c == 'D':
        print("VOLTMETER MODE\nPress ^C to exit")
        while True:
            try:
                print("VOLTAGE PROBE %0.2fV" %
                      (ADCPIN.value / 65535 * ADCPIN.reference_voltage))
                time.sleep(0.1)
            except KeyboardInterrupt:
                print("DONE")
                break
