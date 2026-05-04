from machine import Pin
import neopixel

_pin = Pin(16, Pin.OUT)
_np = neopixel.NeoPixel(_pin, 1)

def set_color(r, g, b):
    # WS2812 uses GRB byte order — swap R and G
    _np[0] = (g, r, b)
    _np.write()

def off():
    set_color(0, 0, 0)