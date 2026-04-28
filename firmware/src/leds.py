from machine import Pin, Timer
import micropython
import config

_pwr_pin     = None
_hdd_pin     = None
_pwr_samples = []   # list of 0/1, max WINDOW_SIZE elements
_hdd_samples = []
_timer       = None


def start_sampling():
    """Start the 5 ms periodic sampler.  Safe to call again to reset the window."""
    global _pwr_pin, _hdd_pin, _timer, _pwr_samples, _hdd_samples

    _pwr_pin     = Pin(config.PWR_LED_PIN, Pin.IN, Pin.PULL_UP)
    _hdd_pin     = Pin(config.HDD_LED_PIN, Pin.IN, Pin.PULL_UP)
    _pwr_samples = []
    _hdd_samples = []

    if _timer is not None:
        try:
            _timer.deinit()
        except Exception:
            pass

    _timer = Timer()
    _timer.init(period=config.SAMPLE_INTERVAL_MS, mode=Timer.PERIODIC, callback=_sample_isr)
    config.log("INFO", "LED sampling started (window={}ms)".format(config.WINDOW_MS))


# --- ISR (keep minimal) ---------------------------------------------------

def _sample_isr(t):
    micropython.schedule(_do_sample, None)


# --- Deferred (main-execution context) ------------------------------------

def _do_sample(arg):
    if _pwr_pin is None or _hdd_pin is None:
        return
    _pwr_samples.append(_pwr_pin.value())
    _hdd_samples.append(_hdd_pin.value())
    # Trim to WINDOW_SIZE — pop(0) is O(n) but list is short (≤300)
    if len(_pwr_samples) > config.WINDOW_SIZE:
        del _pwr_samples[0]
        del _hdd_samples[0]


# --- Classification -------------------------------------------------------

def _classify_pwr(samples):
    if len(samples) < config.WINDOW_SIZE:
        return "unknown"
    transitions = sum(1 for i in range(1, len(samples)) if samples[i] != samples[i - 1])
    if transitions >= 2:
        return "blinking"
    if all(s == 0 for s in samples):
        return "on"
    return "off"


def _classify_hdd(samples):
    if len(samples) < config.WINDOW_SIZE:
        return "unknown"
    for i in range(1, len(samples)):
        if samples[i] != samples[i - 1]:
            return "active"
    return "idle"


def get_status():
    """Return {'pwr': ..., 'hdd': ...} snapshot.  Safe to call from REPL."""
    pwr = list(_pwr_samples)
    hdd = list(_hdd_samples)
    return {
        "pwr": _classify_pwr(pwr),
        "hdd": _classify_hdd(hdd),
    }
