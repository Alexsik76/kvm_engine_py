from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # Project Paths
    project_root: Path = Path(__file__).parent.parent
    mediamtx_path: Path = Path("/home/alex/mediamtx")
    
    # Binary Names/Paths
    hid_server_bin: str = "hid_server"
    kvm_engine_bin: str = "kvm_engine"
    
    # Hardware Configuration
    video_device: str = "/dev/video0"
    edid_path: Path = Path("/home/alex/TC358743-Driver/force_720p.edid")
    
    # HID Server Configuration
    hid_port: int = 8080
    jwt_secret: str = "your_default_jwt_secret"
    keyboard_device: str = "/dev/hidg0"
    mouse_device: str = "/dev/hidg1"
    
    # Logging
    log_level: str = "INFO"