import asyncio
import structlog
from pathlib import Path
from contextlib import asynccontextmanager
from app.hid.server import HIDServer

log = structlog.get_logger()

class ServiceManager:
    def __init__(self, settings):
        self.settings = settings
        self.hid_server = HIDServer(settings)

    @asynccontextmanager
    async def run_process(self, name: str, command: list, cwd: str = None):
        log.info("service_starting", name=name, command=" ".join(command))

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
        config_path = self.settings.project_root / "config" / "mediamtx.yml"
        mediamtx_cmd = ["./mediamtx", str(config_path)]

        # Note: kvm_engine is currently managed by MediaMTX via 'runOnInit' in mediamtx.yml
        # to simplify the ffmpeg piping. 

        async with asyncio.TaskGroup() as tg:
            # 1. Start MediaMTX (handles video pipeline)
            tg.create_task(self._run_mediamtx(mediamtx_cmd))

            # 2. Start Python-based HID Server (handles keyboard/mouse)
            tg.create_task(self._run_internal_hid_server())

    async def _run_mediamtx(self, cmd):
        async with self.run_process("mediamtx", cmd, cwd=self.settings.mediamtx_path) as proc:
            await proc.wait()

    async def _run_internal_hid_server(self):
        log.info("starting_internal_hid_server")
        try:
            await self.hid_server.start()
            # Keep the task alive as long as the server is running
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await self.hid_server.stop()
            raise
        except Exception as e:
            log.error("internal_hid_server_failed", error=str(e))
            await self.hid_server.stop()