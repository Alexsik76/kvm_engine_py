import os
import fcntl
import select
import struct
import asyncio
import structlog
from typing import List

log = structlog.get_logger()

V4L2_EVENT_SOURCE_CHANGE = 5
VIDIOC_SUBSCRIBE_EVENT = 0x4020565A
VIDIOC_DQEVENT = 0x80805659 # Simplified, kernel often uses multiple variants

class VideoSignalMonitor:
    def __init__(self, device_path: str = "/dev/v4l-subdev0"):
        self.device_path = device_path
        self.fd: int | None = None
        self._running = False
        self._subscribers: List[asyncio.Queue] = []
        self._current_status = "unknown"

    def is_active(self) -> bool:
        if self.fd is None:
            return False
        buf = bytearray(256)
        # VIDIOC_SUBDEV_QUERY_DV_TIMINGS = 0x80845663
        try:
            fcntl.ioctl(self.fd, 0x80845663, buf)
            return True
        except OSError as e:
            if e.errno in (37, 67, 61, 71): # ENODATA, ENOLINK, etc.
                return False
            log.error("video_monitor_ioctl_error", errno=e.errno)
            return False

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=10)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @property
    def current_status(self) -> str:
        return self._current_status

    async def start(self):
        if self._running:
            return
        
        try:
            self.fd = os.open(self.device_path, os.O_RDWR | os.O_NONBLOCK)
            # Subscribe to source change events
            sub_data = struct.pack("=III5I", V4L2_EVENT_SOURCE_CHANGE, 0, 0, 0, 0, 0, 0, 0)
            fcntl.ioctl(self.fd, VIDIOC_SUBSCRIBE_EVENT, sub_data)
        except Exception as e:
            log.error("video_monitor_init_failed", error=str(e))
            return

        self._running = True
        self._current_status = "active" if self.is_active() else "inactive"
        log.info("video_monitor_started", initial_status=self._current_status)
        
        asyncio.create_task(self._monitor_loop())

    async def stop(self):
        self._running = False
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        log.info("video_monitor_stopped")

    async def _monitor_loop(self):
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                # Poll in executor to avoid blocking event loop
                await loop.run_in_executor(None, self._poll_events)
                
                # Debounce: wait for signal to stabilize
                await asyncio.sleep(0.25)
                
                new_status = "active" if self.is_active() else "inactive"
                if new_status != self._current_status:
                    self._current_status = new_status
                    log.info("video_signal_changed", status=self._current_status)
                    self._broadcast({"type": "video_status", "status": self._current_status})
            except Exception as e:
                if self._running:
                    log.error("video_monitor_loop_error", error=str(e))
                await asyncio.sleep(1.0)

    def _poll_events(self):
        poller = select.poll()
        poller.register(self.fd, select.POLLPRI)
        events = poller.poll(1000)
        if events:
            # Clear event queue
            buf = bytearray(256)
            for cmd in (0x80805659, 0x80785659, 0x80885659):
                try:
                    fcntl.ioctl(self.fd, cmd, buf)
                    break
                except OSError:
                    continue

    def _broadcast(self, data: dict):
        for q in list(self._subscribers):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass
