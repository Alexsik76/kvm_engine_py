import protocol
import pulse
import config


class UartHandler:
    def __init__(self):
        self._uart         = None
        self._buf          = b""
        self._ping_ready   = False  # True for one poll() cycle after ping/pong

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init(self, uart):
        self._uart = uart

    def poll(self):
        """Read all pending UART bytes and dispatch complete frames.

        Returns True exactly once after a successful ping/pong exchange so
        that main.py can enable streaming; False otherwise.
        """
        if self._uart is None:
            return False

        n = self._uart.any()
        if n:
            data = self._uart.read(n)
            if data:
                self._buf += data

        # Guard against a runaway sender that never sends \\n.
        if len(self._buf) > config.MAX_FRAME_BYTES and b"\n" not in self._buf:
            config.log("ERROR", "rx buffer overflow, discarding")
            self.send({"type": "error", "reason": "frame_too_long"})
            self._buf = b""

        while b"\n" in self._buf:
            idx = self._buf.index(b"\n")
            raw = self._buf[:idx]
            self._buf = self._buf[idx + 1:]
            try:
                line = raw.decode("utf-8")
            except Exception:
                line = ""
            self._handle_line(line)

        if self._ping_ready:
            self._ping_ready = False
            return True
        return False

    def send(self, frame_dict):
        if self._uart is None:
            return
        try:
            self._uart.write(protocol.format_frame(frame_dict).encode("utf-8"))
        except Exception as e:
            config.log("ERROR", "send error: {}".format(e))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_line(self, line):
        if not line.strip():
            return

        if not protocol.check_frame_length(line):
            config.log("ERROR", "frame too long: {} bytes".format(len(line)))
            self.send({"type": "error", "reason": "frame_too_long", "received": line[:20]})
            return

        frame = protocol.parse_frame(line)
        if frame is None:
            config.log("ERROR", "malformed json: '{}'".format(line))
            self.send({"type": "error", "reason": "malformed_json", "received": line[:32]})
            return

        self._dispatch(frame)

    def _dispatch(self, frame):
        t = frame.get("type")
        try:
            if t == "ping":
                self.send({
                    "type":       "pong",
                    "fw_version": config.FW_VERSION,
                    "protocol":   config.PROTOCOL_VERSION,
                })
                self._ping_ready = True
                config.log("INFO", "ping received, pong sent")

            elif t == "power_press":
                def _ack():
                    self.send({"type": "ack", "cmd": "power_press"})
                pulse.start_pulse(config.PWR_BTN_PIN, config.POWER_PRESS_MS, _ack)

            elif t == "power_hold":
                def _ack():
                    self.send({"type": "ack", "cmd": "power_hold"})
                pulse.start_pulse(config.PWR_BTN_PIN, config.POWER_HOLD_MS, _ack)

            elif t == "reset":
                def _ack():
                    self.send({"type": "ack", "cmd": "reset"})
                pulse.start_pulse(config.RST_BTN_PIN, config.RESET_MS, _ack)

            else:
                config.log("ERROR", "unknown command: {}".format(t))
                self.send({
                    "type":     "error",
                    "reason":   "unknown_command",
                    "received": str(t) if t is not None else "",
                })

        except Exception as e:
            config.log("ERROR", "dispatch exception: {}".format(e))
