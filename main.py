# enums
MODE_HIZ = 0

# start in HiZ mode
MODE = MODE_HIZ
# make a mini REPL

HELP_MENU = """\
MENUS
? Help
i Version & status info
M Bus mode
b Terminal speed
G Freq Generator/PWM on AUX"""

VERSION_INFO = """\
Circuit Pyrate v0
www.adafruit.com"""

while True:
    prompt = ""
    if MODE == MODE_HIZ:
        prompt = "HiZ> "
    commands = input(prompt)
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
    elif c == 'b':
        print("No baud rate change required for USB!")
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
