import asyncio
import structlog
from pathlib import Path
from contextlib import asynccontextmanager

log = structlog.get_logger()

class ServiceManager:
    def __init__(self, settings):
        self.settings = settings

    @asynccontextmanager
    async def run_process(self, name: str, command: list, cwd: str = None):
        log.info("service_starting", name=name, command=" ".join(command))

        # Note: Some processes (like hid_server) might require sudo to access /dev/hidg*
        # If running as systemd service, ensure User=root or proper group permissions.
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None
        )

        try:
            yield proc
        finally:
            log.info("service_stopping", name=name)
            if proc.returncode is None:
                proc.terminate()
                await proc.wait()

    async def start_all(self):
        """Orchestrate primary services: MediaMTX and HID Server"""

        # Paths for binaries
        mediamtx_cmd = ["./mediamtx"]
        hid_server_cmd = [str(self.settings.project_root / self.settings.hid_server_bin)]

        # Note: kvm_engine is currently managed by MediaMTX via 'runOnInit' in mediamtx.yml
        # to simplify the ffmpeg piping. 

        async with asyncio.TaskGroup() as tg:
            # 1. Start MediaMTX (handles video pipeline)
            tg.create_task(self._run_mediamtx(mediamtx_cmd))

            # 2. Start HID Server (handles keyboard/mouse)
            tg.create_task(self._run_hid_server(hid_server_cmd))

    async def _run_mediamtx(self, cmd):
        async with self.run_process("mediamtx", cmd, cwd=self.settings.mediamtx_path):
            while True:
                await asyncio.sleep(1)

    async def _run_hid_server(self, cmd):
        async with self.run_process("hid_server", cmd, cwd=self.settings.project_root):
            while True:
                await asyncio.sleep(1)