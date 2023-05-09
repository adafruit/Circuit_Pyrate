import board
import usb_cdc
import adafruit_circuitpyrate
import adafruit_prompt_toolkit as prompt_toolkit

serial = usb_cdc.console
if usb_cdc.data:
    serial = usb_cdc.data

input_wrapper = adafruit_circuitpyrate.BinarySwitcher(serial)

session = prompt_toolkit.PromptSession(input=input_wrapper, output=serial)
pyrate = adafruit_circuitpyrate.Pyrate(input_wrapper, serial, aux_pin=board.A1, adc_pin=board.A0, miso_pin=board.MISO, cs_pin=board.A1, clock_pin=board.SCL, mosi_pin=board.SDA, scl_pin=board.SCL1, sda_pin=board.SDA1)

while True:
    try:
        commands = session.prompt(pyrate.mode.name + "> ")
    except adafruit_circuitpyrate.EnterBinaryMode:
        # This doesn't return until binary mode is exited.
        pyrate.run_binary_mode()
    print("->", commands)
    pyrate.run_commands(commands)
