import subprocess
import os
from pathlib import Path
import httpx
import structlog

log = structlog.get_logger()

class ProjectBuilder:
    def __init__(self, settings):
        self.settings = settings
        self.include_dir = self.settings.project_root / "src" / "video_engine" / "include" / "nlohmann"
        self.json_url = "https://github.com/nlohmann/json/releases/download/v3.12.0/json.hpp"

    async def ensure_dependencies(self):
        if not self.include_dir.exists():
            log.info("dependency_missing", name="nlohmann/json")
            self.include_dir.mkdir(parents=True, exist_ok=True)
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.json_url)
                response.raise_for_status()
                (self.include_dir / "json.hpp").write_bytes(response.content)

    def build_all(self, force_rebuild: bool = False):
        engine_bin = self.settings.project_root / self.settings.kvm_engine_bin

        # Check if binaries already exist to skip redundant steps, unless forced
        if not force_rebuild and engine_bin.exists():
            log.info("binaries_exist", action="skipping_build")
            return

        log.info("build_starting", engine=str(engine_bin))

        # Build C++ Video Engine (Core)
        cpp_source_dir = self.settings.project_root / "src" / "video_engine"
        cpp_include_dir = cpp_source_dir / "include"
        cpp_cmd = [
            "g++", "-O2", "-mcpu=cortex-a72", "-mtune=cortex-a72", "-DDEBUG_TIMING",
            "-I", str(cpp_include_dir),
            str(cpp_source_dir / "main.cpp"), 
            str(cpp_source_dir / "CaptureDevice.cpp"), 
            str(cpp_source_dir / "EncoderDevice.cpp"), 
            str(cpp_source_dir / "Config.cpp"),
            "-o", str(engine_bin)
        ]
        build_tmp = self.settings.project_root / ".build_tmp"
        build_tmp.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["TMPDIR"] = str(build_tmp)
        subprocess.run(cpp_cmd, cwd=self.settings.project_root, check=True, env=env)