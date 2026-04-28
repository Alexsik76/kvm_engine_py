from machine import Pin, Timer
import micropython
import config

# Safe initial state on import — outputs driven low immediately.
_pwr_btn = Pin(config.PWR_BTN_PIN, Pin.OUT, value=0)
_rst_btn = Pin(config.RST_BTN_PIN, Pin.OUT, value=0)

# Active timers keyed by pin number.
_timers = {}


def start_pulse(pin_num, duration_ms, on_complete=None):
    """Drive pin_num high for duration_ms, then low.

    on_complete() is called from main-execution context (not ISR) after the
    pulse ends.  Safe to use for UART I/O.  Parallel pulses on different pins
    are supported; a second call on the same pin cancels the running pulse.
    """
    if pin_num in _timers:
        try:
            _timers[pin_num].deinit()
        except Exception:
            pass

    pin = Pin(pin_num, Pin.OUT)
    pin.value(1)
    config.log("DEBUG", "pulse start: pin=GP{} duration={}ms".format(pin_num, duration_ms))

    t = Timer()
    _timers[pin_num] = t

    def _stop(timer):
        pin.value(0)
        if on_complete is not None:
            micropython.schedule(_invoke, on_complete)

    t.init(mode=Timer.ONE_SHOT, period=duration_ms, callback=_stop)


def _invoke(fn):
    """Trampoline called by micropython.schedule; keeps ISR minimal."""
    try:
        fn()
    except Exception as e:
        config.log("ERROR", "pulse callback error: {}".format(e))
