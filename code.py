import board
import usb_cdc
import adafruit_circuitpyrate
import adafruit_prompt_toolkit as prompt_toolkit

serial = usb_cdc.console
if usb_cdc.data:
    serial = usb_cdc.data

session = prompt_toolkit.PromptSession(input=serial, output=serial)
pyrate = adafruit_circuitpyrate.Pyrate(serial, serial, aux_pin=board.A1, adc_pin=board.A0, miso_pin=board.MISO, cs_pin=board.A1, clock_pin=board.SCL, mosi_pin=board.SDA)

while True:
    commands = session.prompt(pyrate.mode.name + "> ")
    print("->", commands)
    pyrate.run_commands(commands)
