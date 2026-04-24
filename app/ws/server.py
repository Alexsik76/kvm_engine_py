import asyncio
import structlog
from aiohttp import web
from typing import Callable, Awaitable, Any

log = structlog.get_logger()

class WSServer:
    """
    Independent and reusable HTTP/WebSocket server.
    Can be instantiated and used for any task requiring HTTP/WS endpoints.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

    def add_route(self, method: str, path: str, handler: Callable[[web.Request], Awaitable[web.Response]]):
        """Add an HTTP or WebSocket route"""
        self.app.router.add_route(method, path, handler)

    def add_routes(self, routes: list):
        """Add multiple routes at once"""
        self.app.router.add_routes(routes)

    async def start(self):
        """Start the server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        log.info("ws_server_started", host=self.host, port=self.port)

    async def stop(self):
        """Stop the server gracefully"""
        if self.runner:
            await self.runner.cleanup()
            log.info("ws_server_stopped")
