import asyncio
import os
import structlog

log = structlog.get_logger()

class HIDManager:
    def __init__(self, keyboard_device: str, mouse_device: str):
        self.keyboard_device = keyboard_device
        self.mouse_device = mouse_device
        self._lock = asyncio.Lock()
        self._kb_file = None
        self._m_file = None

    def reopen(self):
        """Opens or reopens the device files."""
        if self._kb_file:
            try:
                self._kb_file.close()
            except Exception:
                pass
            self._kb_file = None
            
        if self._m_file:
            try:
                self._m_file.close()
            except Exception:
                pass
            self._m_file = None

        try:
            # We open in wb (write binary) and unbuffered mode (buffering=0)
            self._kb_file = open(self.keyboard_device, "wb", buffering=0)
        except Exception as e:
            log.error("failed_to_open_keyboard", error=str(e), path=self.keyboard_device)
            raise

        try:
            self._m_file = open(self.mouse_device, "wb", buffering=0)
        except Exception as e:
            if self._kb_file:
                self._kb_file.close()
            log.error("failed_to_open_mouse", error=str(e), path=self.mouse_device)
            raise

    async def init(self):
        async with self._lock:
            # Reopening can be blocking, but it's fast. Let's wrap if necessary,
            # but standard open for character devices in Linux is fast.
            self.reopen()

    async def send_key_report(self, modifiers: int, keys: list[int]):
        async with self._lock:
            if not self._kb_file:
                return
            report = bytearray(8)
            report[0] = modifiers
            for i, key in enumerate(keys[:6]):
                report[i + 2] = key

            try:
                self._kb_file.write(report)
            except Exception as e:
                log.error("keyboard_write_error", error=str(e))

    async def send_mouse_report(self, buttons: int, x: int, y: int, wheel: int):
        async with self._lock:
            if not self._m_file:
                return
            
            # Ensure proper signed 8-bit wrap for negative values if they aren't properly masked
            report = bytearray([
                buttons & 0xFF,
                x & 0xFF,
                y & 0xFF,
                wheel & 0xFF
            ])
            try:
                self._m_file.write(report)
            except Exception as e:
                log.error("mouse_write_error", error=str(e))

    async def clear_all(self):
        await self.send_key_report(0, [])
        await self.send_mouse_report(0, 0, 0, 0)

    async def force_reset(self):
        async with self._lock:
            self.reopen()

    async def close(self):
        async with self._lock:
            if self._kb_file:
                try:
                    # Write empty report before closing
                    self._kb_file.write(bytearray(8))
                    self._kb_file.close()
                except Exception:
                    pass
            if self._m_file:
                try:
                    self._m_file.write(bytearray(4))
                    self._m_file.close()
                except Exception:
                    pass
