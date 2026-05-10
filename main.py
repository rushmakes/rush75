import board
import neopixel
import time
import math
import random
from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.scanners import DiodeOrientation
from kmk.modules.encoder import EncoderHandler
from kmk.modules.layers import Layers
from kmk.extensions.media_keys import MediaKeys

keyboard = KMKKeyboard()
keyboard.extensions.append(MediaKeys())
keyboard.modules.append(Layers())

# ── Matrix pins ───────────────────────────────────────────────────────────────
keyboard.col_pins = (
    board.GP7,  board.GP8,  board.GP9,  board.GP10, board.GP11,
    board.GP12, board.GP13, board.GP14, board.GP15, board.GP16,
    board.GP17, board.GP18, board.GP19, board.GP20, board.GP21,
    board.GP22, board.GP26,
)
keyboard.row_pins = (
    board.GP0, board.GP1, board.GP2, board.GP3,
    board.GP4, board.GP5,
)
keyboard.diode_orientation = DiodeOrientation.COL2ROW

# ── Encoder ───────────────────────────────────────────────────────────────────
encoder_handler = EncoderHandler()
keyboard.modules.append(encoder_handler)
encoder_handler.pins = ((board.GP27, board.GP28, None, True),)
encoder_handler.map = (
    ((KC.AUDIO_VOL_UP, KC.AUDIO_VOL_DOWN, KC.AUDIO_MUTE),),  # Layer 0
    ((KC.AUDIO_VOL_UP, KC.AUDIO_VOL_DOWN, KC.AUDIO_MUTE),),  # Layer 1 Fn
)

# ── WS2812 setup ──────────────────────────────────────────────────────────────
NUM_LEDS        = 20
CAPSLOCK_LED    = 0
BRIGHTNESS      = 0.3

pixels = neopixel.NeoPixel(
    board.GP6,
    NUM_LEDS,
    brightness=BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB,
)

# ── Layer colors (used by Static and as base hue for others) ──────────────────
LAYER_COLORS = {
    0: (0,   0,   255),   # Base → Blue
    1: (255, 0,   0  ),   # Fn   → Red
}

CAPSLOCK_ON_COLOR  = (255, 255, 255)  # White
CAPSLOCK_OFF_COLOR = (0,   0,   0  )  # Off

# ── Animation state ───────────────────────────────────────────────────────────
ANIM_STATIC   = 0
ANIM_BREATHE  = 1
ANIM_RAINBOW  = 2
ANIM_SPARKLE  = 3
ANIM_NAMES    = ["Static", "Breathing", "Rainbow Wave", "Sparkle"]

current_anim  = 0          # active animation index
anim_step     = 0.0        # shared step counter for time-based animations
last_tick     = time.monotonic()
TICK_RATE     = 0.03       # seconds between animation frames (~33 fps)

# Sparkle state
sparkle_leds  = [0.0] * NUM_LEDS   # per-LED brightness 0.0–1.0

# ── Helpers ───────────────────────────────────────────────────────────────────
def hsv_to_rgb(h, s, v):
    """Convert HSV (0–1 each) to RGB tuple (0–255 each)."""
    if s == 0:
        c = int(v * 255)
        return (c, c, c)
    i = int(h * 6)
    f = h * 6 - i
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    i %= 6
    if i == 0: r, g, b = v, t, p
    elif i == 1: r, g, b = q, v, p
    elif i == 2: r, g, b = p, v, t
    elif i == 3: r, g, b = p, q, v
    elif i == 4: r, g, b = t, p, v
    else:        r, g, b = v, p, q
    return (int(r * 255), int(g * 255), int(b * 255))

def scale_color(color, factor):
    """Scale an RGB tuple brightness by factor (0.0–1.0)."""
    return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))

def get_caps_state():
    """Return True if CapsLock is active."""
    try:
        return bool(keyboard.led_status & 0x02)
    except AttributeError:
        return False

def get_layer_color():
    """Return color for the current active layer."""
    layer = keyboard.active_layers[0] if keyboard.active_layers else 0
    return LAYER_COLORS.get(layer, (0, 255, 0))

def set_capslock_led():
    """Always set LED 0 to CapsLock state regardless of animation."""
    pixels[CAPSLOCK_LED] = CAPSLOCK_ON_COLOR if get_caps_state() else CAPSLOCK_OFF_COLOR

# ── Animation renderers ───────────────────────────────────────────────────────
def render_static():
    color = get_layer_color()
    for i in range(1, NUM_LEDS):
        pixels[i] = color

def render_breathe():
    # Sine wave from 0.05 to 1.0 brightness
    factor = (math.sin(anim_step * 2 * math.pi) + 1) / 2  # 0.0–1.0
    factor = 0.05 + factor * 0.95
    color = scale_color(get_layer_color(), factor)
    for i in range(1, NUM_LEDS):
        pixels[i] = color

def render_rainbow():
    # Each LED offset along the hue wheel, wave moves over time
    for i in range(1, NUM_LEDS):
        hue = (anim_step + i / NUM_LEDS) % 1.0
        pixels[i] = hsv_to_rgb(hue, 1.0, 1.0)

def render_sparkle():
    global sparkle_leds
    # Randomly ignite LEDs, fade all down each frame
    for i in range(1, NUM_LEDS):
        # Random chance to light up
        if random.random() < 0.08:
            sparkle_leds[i] = 1.0
        else:
            sparkle_leds[i] = max(0.0, sparkle_leds[i] - 0.08)
        pixels[i] = scale_color(get_layer_color(), sparkle_leds[i])

RENDERERS = [render_static, render_breathe, render_rainbow, render_sparkle]

# Animation step speeds
ANIM_SPEEDS = {
    ANIM_STATIC:  0.0,    # no movement
    ANIM_BREATHE: 0.008,  # slow pulse
    ANIM_RAINBOW: 0.005,  # smooth wave
    ANIM_SPARKLE: 0.0,    # speed handled per-frame
}

# ── Custom key: cycle animation ───────────────────────────────────────────────
def cycle_animation(*args, **kwargs):
    global current_anim, sparkle_leds, anim_step
    current_anim = (current_anim + 1) % len(ANIM_NAMES)
    anim_step = 0.0
    sparkle_leds = [0.0] * NUM_LEDS
    print(f"Animation: {ANIM_NAMES[current_anim]}")
    return keyboard

ANIM_NEXT = KC.make_key(
    names=("ANIM_NEXT",),
    on_press=cycle_animation,
)

# ── Keyboard lifecycle hook ───────────────────────────────────────────────────
_original_before_hid_send = keyboard.before_hid_send

def before_hid_send(kb):
    global anim_step, last_tick
    _original_before_hid_send(kb)

    now = time.monotonic()
    if now - last_tick >= TICK_RATE:
        last_tick = now
        anim_step = (anim_step + ANIM_SPEEDS[current_anim]) % 1.0
        RENDERERS[current_anim]()
        set_capslock_led()
        pixels.show()

keyboard.before_hid_send = before_hid_send

# ── Aliases ───────────────────────────────────────────────────────────────────
___ = KC.TRNS
FN  = KC.MO(1)

# ── Keymap ────────────────────────────────────────────────────────────────────
keyboard.keymap = [

    # ════════════════════════════════════════════════════════
    #  LAYER 0 – Base
    # ════════════════════════════════════════════════════════
    [
        # Row 0 – Function row
        # 0        1        2        3        4        5        6        7        8        9        10       11       12       13       14       15       16
        KC.ESC,  KC.F1,   KC.F2,   KC.F3,   KC.F4,   KC.F5,   KC.F6,   KC.F7,   KC.F8,   KC.F9,   KC.F10,  KC.F11,  KC.F12,  ___,     KC.HOME, ___,     KC.MUTE,

        # Row 1 – Number row
        KC.GRV,  KC.N1,   KC.N2,   KC.N3,   KC.N4,   KC.N5,   KC.N6,   KC.N7,   KC.N8,   KC.N9,   KC.N0,   KC.MINS, KC.EQL,  KC.BSPC, ___,     ___,     KC.PGUP,

        # Row 2 – QWERTY (Tab=col0, ___=col1, Q=col2)
        KC.TAB,  ___,     KC.Q,    KC.W,    KC.E,    KC.R,    KC.T,    KC.Y,    KC.U,    KC.I,    KC.O,    KC.P,    KC.LBRC, KC.RBRC, KC.BSLS, ___,     KC.PGDN,

        # Row 3 – Home row (Caps=col0, ___=col1, A=col2)
        KC.CAPS, ___,     KC.A,    KC.S,    KC.D,    KC.F,    KC.G,    KC.H,    KC.J,    KC.K,    KC.L,    KC.SCLN, KC.QUOT, ___,     KC.ENT,  ___,     KC.END,

        # Row 4 – Shift row
        KC.LSFT, ___,     KC.Z,    KC.X,    KC.C,    KC.V,    KC.B,    KC.N,    KC.M,    KC.COMM, KC.DOT,  KC.SLSH, ___,     KC.RSFT, ___,     ___,     KC.DEL,

        # Row 5 – Bottom row
        KC.LCTL, KC.LGUI, KC.LALT, ___,     ___,     ___,     KC.SPC,  ___,     ___,     ___,     KC.RALT, FN,      KC.RCTL, ___,     ___,     KC.UP,   ___,
    ],

    # ════════════════════════════════════════════════════════
    #  LAYER 1 – Fn
    # ════════════════════════════════════════════════════════
    [
        # Row 0 – Fn + F-keys → media
        ___,     KC.AUDIO_MUTE, KC.AUDIO_VOL_DOWN, KC.AUDIO_VOL_UP, KC.MPLY, KC.MPRV, KC.MNXT, ___,     ___,     ___,     ___,     ___,     KC.INS,  ___,     ___,     ___,     ___,

        # Row 1 – Fn + Backspace → Delete
        ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     KC.DEL,  ___,     ___,     ___,

        # Row 2
        ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,

        # Row 3 – Fn + A (col=2) → cycle animation
        ___,     ___,     ANIM_NEXT, ___,   ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,

        # Row 4
        ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,

        # Row 5 – Fn + Up → PgUp
        ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     ___,     KC.PGUP, ___,
    ],
]

# ── Initial render ────────────────────────────────────────────────────────────
render_static()
set_capslock_led()
pixels.show()

keyboard.go()
