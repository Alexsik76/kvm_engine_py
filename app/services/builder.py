import subprocess
from pathlib import Path
import httpx
import structlog

log = structlog.get_logger()

class ProjectBuilder:
    def __init__(self, settings):
        self.settings = settings
        self.include_dir = Path(settings.project_root) / "include" / "nlohmann"
        self.json_url = "https://github.com/nlohmann/json/releases/download/v3.12.0/json.hpp"

    async def ensure_dependencies(self):
        if not self.include_dir.exists():
            log.info("dependency_missing", name="nlohmann/json")
            self.include_dir.mkdir(parents=True, exist_ok=True)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(self.json_url)
                response.raise_for_status()
                (self.include_dir / "json.hpp").write_bytes(response.content)

    def build_all(self):
        engine_bin = Path(self.settings.project_root) / "kvm_engine"
        hid_bin = Path(self.settings.hid_server_bin)

        # Check if binaries already exist to skip redundant steps
        if engine_bin.exists() and hid_bin.exists():
            log.info("binaries_exist", action="skipping_build")
            return

        cpp_cmd = [
            "g++", "-O3", "-mcpu=cortex-a72", "-mtune=cortex-a72", "-flto=auto",
            "-I", str(Path(self.settings.project_root) / "include"),
            "src/main.cpp", "src/CaptureDevice.cpp", "src/EncoderDevice.cpp", "src/Config.cpp",
            "-o", str(engine_bin)
        ]
        subprocess.run(cpp_cmd, cwd=self.settings.project_root, check=True)

        go_cmd = ["go", "build", "-o", str(hid_bin), "main.go"]
        subprocess.run(go_cmd, cwd=Path(self.settings.project_root) / "src" / "hid_server", check=True)