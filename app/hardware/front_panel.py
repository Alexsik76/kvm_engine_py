import asyncio
import json
import structlog
import serial_asyncio
from serial import SerialException

log = structlog.get_logger()

EXPECTED_PROTOCOL = 1
PROBE_DELAYS_S = [0.2, 0.4, 0.8, 1.6, 3.0]
PROBE_TIMEOUT_S = 0.5
MAX_FRAME_LEN = 256
SUBSCRIBER_QUEUE_SIZE = 32


class FrontPanelNotConnectedError(RuntimeError):
    """Attempt to issue a command when the board is unavailable."""


class FrontPanelClient:
    def __init__(self, port: str, baudrate: int):
        self._port = port
        self._baudrate = baudrate
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> bool:
        """
        Probe sequence per protocol section 4:
        5 attempts with back-off delays 200, 400, 800, 1600, 3000 ms.
        Per-attempt timeout: 500 ms.
        Returns True on first successful pong, False after all 5 failures.
        """
        for attempt, delay in enumerate(PROBE_DELAYS_S, start=1):
            log.info("front_panel_probe_attempt", attempt=attempt, total=len(PROBE_DELAYS_S))
            try:
                if not self.is_open:
                    self._reader, self._writer = await serial_asyncio.open_serial_connection(
                        url=self._port, baudrate=self._baudrate
                    )
                await self.send_command("ping")
                frame = await asyncio.wait_for(self.read_frame(), timeout=PROBE_TIMEOUT_S)
                if frame and frame.get("type") == "pong":
                    protocol = frame.get("protocol")
                    fw_version = frame.get("fw_version", "?")
                    if protocol != EXPECTED_PROTOCOL:
                        log.warning(
                            "front_panel_protocol_mismatch",
                            board=protocol,
                            expected=EXPECTED_PROTOCOL,
                        )
                    log.info("front_panel_connected", fw_version=fw_version, protocol=protocol)
                    return True
            except asyncio.TimeoutError:
                log.debug("front_panel_probe_timeout", attempt=attempt)
            except Exception as e:
                log.warning("front_panel_probe_error", attempt=attempt, error=str(e))
            await asyncio.sleep(delay)

        await self.close()
        return False

    async def send_command(self, cmd_type: str) -> None:
        """Writes {"type": cmd_type}\\n to the port. Does not wait for a response."""
        if self._writer is None:
            raise SerialException("Port is not open")
        self._writer.write((json.dumps({"type": cmd_type}) + "\n").encode())
        await self._writer.drain()

    async def read_frame(self) -> dict | None:
        """
        Reads one newline-delimited frame from the stream and parses it as JSON.
        Invalid JSON: logs WARN and returns None.
        Closed port: raises an exception for the caller to handle.
        """
        if self._reader is None:
            raise SerialException("Port is not open")
        line = await self._reader.readline()
        if not line:
            raise SerialException("Serial port closed")
        if len(line) > MAX_FRAME_LEN:
            log.warning("front_panel_frame_too_long", length=len(line))
            return None
        try:
            return json.loads(line.decode("utf-8").strip())
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.warning("front_panel_invalid_frame", error=str(e))
            return None

    async def close(self) -> None:
        """Closes the serial port cleanly. Idempotent."""
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

    @property
    def is_open(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()


class FrontPanelController:
    def __init__(self, settings):
        self._settings = settings
        self._client = FrontPanelClient(
            port=settings.front_panel_port,
            baudrate=settings.front_panel_baudrate,
        )
        self._is_connected = False
        self._last_status: dict | None = None
        self._subscribers: list[asyncio.Queue] = []
        self._read_task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self._settings.front_panel_enabled:
            log.info("front_panel_disabled_in_config")
            return
        if await self._client.connect():
            self._is_connected = True
            self._read_task = asyncio.create_task(self._read_loop())
            log.info("front_panel_started")
        else:
            log.warning("front_panel_not_detected", attempts=len(PROBE_DELAYS_S))

    async def stop(self) -> None:
        if self._read_task is not None and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
        await self._client.close()

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def power_press(self) -> None:
        """Sends power_press command. Raises FrontPanelNotConnectedError if not connected."""
        if not self._is_connected:
            raise FrontPanelNotConnectedError("front-panel not connected")
        await self._client.send_command("power_press")

    async def power_hold(self) -> None:
        if not self._is_connected:
            raise FrontPanelNotConnectedError("front-panel not connected")
        await self._client.send_command("power_hold")

    async def reset(self) -> None:
        if not self._is_connected:
            raise FrontPanelNotConnectedError("front-panel not connected")
        await self._client.send_command("reset")

    def get_status(self) -> dict | None:
        """Returns a copy of the last received led_status frame. None until the first frame arrives."""
        return dict(self._last_status) if self._last_status is not None else None

    def subscribe(self) -> asyncio.Queue:
        """Registers a new queue for led_status fan-out. Returns the created queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Removes a queue from the subscriber list. Idempotent."""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    async def _read_loop(self) -> None:
        try:
            while True:
                frame = await self._client.read_frame()
                if frame is None:
                    continue
                frame_type = frame.get("type")
                if frame_type == "led_status":
                    self._last_status = {
                        "pwr": frame.get("pwr", "unknown"),
                        "hdd": frame.get("hdd", "unknown"),
                    }
                    for q in list(self._subscribers):
                        try:
                            q.put_nowait(dict(self._last_status))
                        except asyncio.QueueFull:
                            log.warning("front_panel_subscriber_queue_full")
                elif frame_type == "ack":
                    log.debug("front_panel_ack", cmd=frame.get("cmd"))
                elif frame_type == "error":
                    log.warning(
                        "front_panel_error_from_board",
                        reason=frame.get("reason"),
                        received=frame.get("received"),
                    )
                elif frame.get("type") == "pong":
                    log.debug("front_panel_late_pong", frame=frame)
                else:
                    log.warning("front_panel_unexpected_frame", frame=frame)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error("front_panel_serial_error", error=str(e))
            self._is_connected = False
