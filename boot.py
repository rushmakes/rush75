import usb_hid
import supervisor
import storage
import usb_cdc

# ── Custom USB device name ────────────────────────────────────────────────────
supervisor.set_usb_identification(
    manufacturer="YourName",        # change to your name or brand
    product="Custom KMK Keyboard",  # change to whatever you want
    vid=0x1209,                     # open-source VID (pid.codes)
    pid=0x0001,                     # change if you have multiple devices
)

# ── Hide CIRCUITPY drive (no more G: drive popup) ────────────────────────────
storage.disable_usb_drive()

# ── Hide serial/REPL COM port (no more COM3 in Device Manager) ───────────────
usb_cdc.disable()

# ── Enable HID devices only ───────────────────────────────────────────────────
usb_hid.enable(
    (
        usb_hid.Device.KEYBOARD,
        usb_hid.Device.CONSUMER_CONTROL,
        usb_hid.Device.MOUSE,
    )
)
