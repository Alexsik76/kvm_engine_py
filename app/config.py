import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

log = structlog.get_logger()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # Project Paths
    project_root: Path = Path(__file__).parent.parent
    mediamtx_path: Path = Path("/home/alex/mediamtx")
    
    # Binary Names/Paths
    hid_server_bin: str = "hid_server"
    kvm_engine_bin: str = "kvm_engine"
    
    # Hardware Configuration
    video_device: str = "/dev/video0"
    edid_path: Path = Path("/home/alex/TC358743-Driver/force_720p.edid")
    
    # HID Server Configuration (loaded from config.json)
    hid_port: int = 8080
    jwt_secret: str = "your_default_jwt_secret"
    keyboard_device: str = "/dev/hidg0"
    mouse_device: str = "/dev/hidg1"
    
    # Logging
    log_level: str = "INFO"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_json_config()

    def _load_json_config(self):
        config_path = self.project_root / "config" / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    server_cfg = data.get("server", {})
                    
                    if "port" in server_cfg:
                        self.hid_port = server_cfg["port"]
                    if "jwt_secret" in server_cfg:
                        self.jwt_secret = server_cfg["jwt_secret"]
                    if "keyboard_device" in server_cfg:
                        self.keyboard_device = server_cfg["keyboard_device"]
                    if "mouse_device" in server_cfg:
                        self.mouse_device = server_cfg["mouse_device"]
            except Exception as e:
                log.error("failed_to_load_json_config", error=str(e))