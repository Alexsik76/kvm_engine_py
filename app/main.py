import asyncio
import click
import structlog
import sys
import subprocess
import traceback
from app.config import Settings
from app.services.manager import ServiceManager
from app.services.builder import ProjectBuilder
from app.hardware.manager import HardwareManager

def setup_logging():
    renderer = structlog.dev.ConsoleRenderer() if sys.stderr.isatty() else structlog.processors.JSONRenderer()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.dev.set_exc_info,
            renderer,
        ]
    )

@click.group()
def cli():
    """IP-KVM Orchestrator CLI"""
    setup_logging()

@cli.command()
@click.option("--build", is_flag=True, help="Rebuild components before start")
@click.option("--no-hw", is_flag=True, help="Skip hardware initialization (e.g. for testing on PC)")
def run(build: bool, no_hw: bool):
    """Start the KVM engine and all services"""
    settings = Settings.from_file()
    log = structlog.get_logger()

    async def _startup():
        # 1. Build Layer
        if build:
            builder = ProjectBuilder(settings)
            await builder.ensure_dependencies()
            try:
                builder.build_all(force_rebuild=True)
                log.info("build_complete")
            except subprocess.CalledProcessError as e:
                log.error("build_failed", error=str(e))
                sys.exit(1)

        # 2. Hardware Layer
        if not no_hw:
            hw_manager = HardwareManager(settings)
            try:
                hw_manager.setup_usb_gadget()
                await hw_manager.init_v4l2()
                log.info("hardware_initialized")
            except Exception as e:
                log.error("hardware_init_failed", error=str(e))
                sys.exit(1)

        # 3. Service Layer
        manager = ServiceManager(settings)
        log.info("kvm_orchestrator_started")
        await manager.start_all()

    try:
        asyncio.run(_startup())
    except KeyboardInterrupt:
        log.info("shutdown_by_user")
    except Exception as e:
        log.error("fatal_error", error=str(e), traceback=traceback.format_exc())
        sys.exit(1)

@cli.command()
def wake():
    """Send a wakeup signal to the host OS"""
    settings = Settings.from_file()
    hw_manager = HardwareManager(settings)
    hw_manager.force_rebind_gadget()
    hw_manager.wake_host()

if __name__ == "__main__":
    cli()
