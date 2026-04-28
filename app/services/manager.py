import asyncio
import structlog
from contextlib import asynccontextmanager
from functools import partial

from app.ws.server import WSServer
from app.hid.server import HIDServer
from app.hardware.front_panel import FrontPanelController
from app.hardware.front_panel_ws import front_panel_ws_handler

log = structlog.get_logger()


class ServiceManager:
    def __init__(self, settings, hw_manager=None):
        self.settings = settings
        self.ws_server = WSServer(port=settings.hid_port)
        self.front_panel = FrontPanelController(settings)
        self.hid_server = HIDServer(settings, ws_server=self.ws_server)
        self.ws_server.add_route(
            "GET",
            "/ws/front_panel",
            partial(
                front_panel_ws_handler,
                controller=self.front_panel,
                jwt_secret=settings.jwt_secret,
            ),
        )

        if hw_manager is not None:
            from app.hardware.wake_handler import make_wake_handler
            self.ws_server.add_route(
                "POST",
                "/ws/wake",
                make_wake_handler(hw_manager, settings.jwt_secret),
            )

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
        config_path = self.settings.project_root / "config" / "mediamtx.yml"
        mediamtx_cmd = ["./mediamtx", str(config_path)]

        # kvm_engine is launched by MediaMTX via runOnDemand in mediamtx.yml
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._run_mediamtx(mediamtx_cmd))
            tg.create_task(self._run_ws_server())
            tg.create_task(self._run_hid_server())
            tg.create_task(self._run_front_panel())

    async def _run_mediamtx(self, cmd):
        async with self.run_process("mediamtx", cmd, cwd=self.settings.mediamtx_path) as proc:
            await proc.wait()

    async def _run_ws_server(self):
        log.info("starting_ws_server")
        try:
            await self.ws_server.start()
            await self.ws_server.wait_closed()
        except asyncio.CancelledError:
            await self.ws_server.stop()
            raise
        except Exception as e:
            log.error("ws_server_failed", error=str(e))
            await self.ws_server.stop()

    async def _run_hid_server(self):
        log.info("starting_internal_hid_server")
        try:
            await self.hid_server.start()
            await asyncio.Event().wait()
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
