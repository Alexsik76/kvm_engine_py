import asyncio
import structlog
from contextlib import asynccontextmanager

log = structlog.get_logger()

class ServiceManager:
    def __init__(self, settings):
        self.settings = settings

    @asynccontextmanager
    async def run_process(self, name: str, command: list, cwd: str = None):
        log.info("service_starting", name=name)
        
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

    async def start_engine(self):
        # Entry point for service orchestration
        async with self.run_process(
            "mediamtx", 
            ["./mediamtx"], 
            cwd=self.settings.mediamtx_path
        ):
            while True:
                await asyncio.sleep(1)