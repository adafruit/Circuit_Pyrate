import usb_cdc
import digitalio
import board
import time
import storage

mode_switch = digitalio.DigitalInOut(board.MODE_SWITCH)
mode_switch.switch_to_input(pull=digitalio.Pull.UP)
time.sleep(0.1)

programmable = mode_switch.value

usb_cdc.enable(console=programmable, data=True)    # Enable console and data
if not programmable:
    storage.disable_usb_drive()
