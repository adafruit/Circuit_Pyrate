import board
import usb_cdc
import digitalio
import adafruit_circuitpyrate
import adafruit_prompt_toolkit as prompt_toolkit

serial = usb_cdc.console
if usb_cdc.data:
    serial = usb_cdc.data

input_wrapper = adafruit_circuitpyrate.BinarySwitcher(serial)
tx_led = digitalio.DigitalInOut(board.TX_LED)
rx_led = digitalio.DigitalInOut(board.RX_LED)
led_toggler = adafruit_circuitpyrate.LEDToggler(input_wrapper, tx_led=tx_led, rx_led=rx_led)

session = prompt_toolkit.PromptSession(input=led_toggler, output=led_toggler)
pyrate = adafruit_circuitpyrate.Pyrate(
    input_wrapper,
    serial,
    aux_pin=board.AUX,
    adc_pin=board.ADC,
    miso_pin=board.MISO,
    cs_pin=board.CS,
    clock_pin=board.CLK,
    mosi_pin=board.MOSI,
    enable_5v_pin=board.ENABLE_5V,
    enable_3v_pin=board.ENABLE_3V3,
    measure_5v_pin=board.MEASURE_5V,
    measure_3v_pin=board.MEASURE_3V3,
    vextern_pin=board.VEXTERN,
    enable_pullups_pin=board.ENABLE_PULLUPS,
    mode_led_pin=board.MODE_LED,
    scl_pin=board.STEMMA_SCL,
    sda_pin=board.STEMMA_SDA,
)

while True:
    try:
        commands = session.prompt(pyrate.mode.name + "> ")
    except adafruit_circuitpyrate.EnterBinaryMode:
        # This doesn't return until binary mode is exited.
        pyrate.run_binary_mode()
    print("->", commands)
    pyrate.run_commands(commands)
