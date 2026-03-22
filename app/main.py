import asyncio
import click
import structlog
import sys
import subprocess
from app.config import Settings
from app.services.manager import ServiceManager
from app.services.builder import ProjectBuilder

def setup_logging():
    renderer = structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.set_exc_info,
            renderer,
        ]
    )

@click.command()
@click.option("--build", is_flag=True, help="Rebuild components before start")
def main(build: bool):
    setup_logging()
    settings = Settings()
    log = structlog.get_logger()
    
    if build:
        builder = ProjectBuilder(settings)
        asyncio.run(builder.ensure_dependencies())
        try:
            builder.build_all()
            log.info("build_complete")
        except subprocess.CalledProcessError as e:
            log.error("build_failed", error=str(e))
            sys.exit(1)

    manager = ServiceManager(settings)
    log.info("kvm_orchestrator_started")

    try:
        asyncio.run(manager.start_engine())
    except KeyboardInterrupt:
        log.info("shutdown_by_user")
    except Exception as e:
        log.error("fatal_error", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()