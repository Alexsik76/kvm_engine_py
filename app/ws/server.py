import asyncio
import structlog
from aiohttp import web
from typing import Callable, Awaitable, Sequence

log = structlog.get_logger()

class WSServer:
    """Independent, reusable HTTP/WebSocket server backed by aiohttp."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None
        self._stop_event: asyncio.Event | None = None

    def add_route(self, method: str, path: str, handler: Callable[[web.Request], Awaitable[web.StreamResponse]]):
        self.app.router.add_route(method, path, handler)

    def add_routes(self, routes: Sequence[web.AbstractRouteDef]):
        self.app.router.add_routes(routes)

    async def start(self):
        if self.runner is not None:
            raise RuntimeError("WSServer already running")
        self._stop_event = asyncio.Event()
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        log.info("ws_server_started", host=self.host, port=self.port)

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            if self._stop_event:
                self._stop_event.set()
            log.info("ws_server_stopped")

    async def wait_closed(self):
        """Suspends until stop() is called."""
        if self._stop_event is None:
            raise RuntimeError("WSServer not started")
        await self._stop_event.wait()
