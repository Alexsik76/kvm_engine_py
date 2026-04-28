# Manual REPL verification script
# Run each block interactively in Thonny REPL after uploading firmware.
# Expected output is shown in comments.

# ------------------------------------------------------------------
# Block 1: protocol — pure-function checks (no hardware needed)
# ------------------------------------------------------------------
import protocol

f = protocol.parse_frame('{"type":"ping"}')
assert f == {"type": "ping"}, f

assert protocol.parse_frame("not json") is None
assert protocol.parse_frame("") is None

assert protocol.check_frame_length('{"type":"ping"}') is True
assert protocol.check_frame_length("x" * 256) is False  # 256 chars + \n > 256 bytes

s = protocol.format_frame({"type": "pong", "fw_version": "1.0", "protocol": 1})
assert s.endswith("\n"), repr(s)
print("protocol OK")

# ------------------------------------------------------------------
# Block 2: pulse — hardware required (GP2 = PWR_BTN)
# ------------------------------------------------------------------
import config; config.AUTO_START = False  # prevent main loop
import pulse
from machine import Pin
import time

pulse.start_pulse(2, 200)     # GP2 high for 200 ms
time.sleep_ms(100)
assert Pin(2).value() == 1, "GP2 should be high mid-pulse"
time.sleep_ms(200)
assert Pin(2).value() == 0, "GP2 should be low after pulse"
print("pulse GP2 OK")

# Test on_complete callback
_done = []
pulse.start_pulse(3, 100, lambda: _done.append(1))  # GP3 = RST_BTN
time.sleep_ms(300)
assert _done == [1], "on_complete not called: {}".format(_done)
print("pulse callback OK")

# ------------------------------------------------------------------
# Block 3: leds — reads GP4/GP5 (pull-down = off)
# ------------------------------------------------------------------
import leds
import time

leds.start_sampling()
time.sleep_ms(200)
s = leds.get_status()
assert s["pwr"] == "unknown", s  # window not yet full
assert s["hdd"] == "unknown", s
print("leds unknown during fill OK")

time.sleep_ms(1400)              # wait for window to fill (1500 ms total)
s = leds.get_status()
assert s["pwr"] in ("off", "on", "blinking"), s
assert s["hdd"] in ("idle", "active"), s
print("leds after fill:", s)

# ------------------------------------------------------------------
# Block 4: uart_handler — loopback via software (no Pi needed)
# ------------------------------------------------------------------
import protocol
from uart_handler import UartHandler

# Minimal fake UART for testing
class FakeUart:
    def __init__(self, data):
        self._data = data
        self.written = b""
    def read(self):
        d = self._data; self._data = b""; return d
    def any(self):
        return len(self._data)
    def write(self, b):
        self.written += b

uart = FakeUart(b'{"type":"ping"}\n')
h = UartHandler()
h.init(uart)
got_ping = h.poll()
assert got_ping is True, "poll() should return True after ping"
resp = protocol.parse_frame(uart.written.decode().strip())
assert resp == {"type": "pong", "fw_version": "1.0", "protocol": 1}, resp
print("uart_handler ping/pong OK")

uart2 = FakeUart(b'{"type":"bad_cmd"}\n')
h2 = UartHandler()
h2.init(uart2)
h2.poll()
err = protocol.parse_frame(uart2.written.decode().strip())
assert err["type"] == "error" and err["reason"] == "unknown_command", err
print("uart_handler unknown_command OK")

print("All REPL checks passed.")
