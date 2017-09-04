# enums
MODE_HIZ = 0

# start in HiZ mode
MODE = MODE_HIZ
# make a mini REPL

HELP_MENU = """\
MENUS
? Help
I Version & status info
M Bus mode
B Terminal speed
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

    c = commands[0].upper()
    commands = commands[1:]
    if c == '?':
        print(HELP_MENU)
    if c == 'I':
        import uos
        print(VERSION_INFO)
        print("Hardware: "+uos.uname().machine)
        print("CircuitPython: "+uos.uname().version)
    if c == 'B':
        print("No baud rate change required for USB!")
