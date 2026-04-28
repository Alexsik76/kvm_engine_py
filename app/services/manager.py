import asyncio
import structlog
from contextlib import asynccontextmanager
from app.hid.server import HIDServer
from app.hardware.front_panel import FrontPanelController

log = structlog.get_logger()

class ServiceManager:
    def __init__(self, settings):
        self.settings = settings
        self.hid_server = HIDServer(settings)
        self.front_panel = FrontPanelController(settings)

    @asynccontextmanager
    async def run_process(self, name: str, command: list, cwd: str | None = None):
        log.info("service_starting", name=name, command=" ".join(command))
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
        )
        try:
            yield proc
        finally:
            log.info("service_stopping", name=name)
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    log.warning("service_force_kill", name=name)
                    proc.kill()
                    await proc.wait()

    async def start_all(self):
        """Orchestrates primary services: MediaMTX and internal HID Server."""
        config_path = self.settings.project_root / "config" / "mediamtx.yml"
        mediamtx_cmd = ["./mediamtx", str(config_path)]

        # kvm_engine is launched by MediaMTX via runOnDemand in mediamtx.yml
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._run_mediamtx(mediamtx_cmd))
            tg.create_task(self._run_internal_hid_server())
            tg.create_task(self._run_front_panel())

    async def _run_mediamtx(self, cmd):
        async with self.run_process("mediamtx", cmd, cwd=self.settings.mediamtx_path) as proc:
            await proc.wait()

    async def _run_internal_hid_server(self):
        log.info("starting_internal_hid_server")
        try:
            await self.hid_server.start()
            await self.hid_server.wait_closed()
        except asyncio.CancelledError:
            await self.hid_server.stop()
            raise
        except Exception as e:
            log.error("internal_hid_server_failed", error=str(e))
            await self.hid_server.stop()

    async def _run_front_panel(self):
        log.info("starting_front_panel")
        try:
            await self.front_panel.start()
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await self.front_panel.stop()
            raise
        except Exception as e:
            log.error("front_panel_failed", error=str(e))
            await self.front_panel.stop()
