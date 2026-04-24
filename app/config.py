import json
from pathlib import Path
from pydantic import BaseModel
import structlog

log = structlog.get_logger()

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "config.json"


class Settings(BaseModel):
    project_root: Path = _PROJECT_ROOT

    # [paths]
    mediamtx_path: Path = Path("/opt/mediamtx")
    edid_path: Path = Path("/etc/kvm/force_720p.edid")
    kvm_engine_bin: str = "kvm_engine"

    # [video]
    video_device: str = "/dev/video0"

    # [hid]
    hid_port: int = 8080
    jwt_secret: str = ""
    keyboard_device: str = "/dev/hidg0"
    mouse_device: str = "/dev/hidg1"

    # [logging]
    log_level: str = "INFO"

    @classmethod
    def from_file(cls, path: Path = _DEFAULT_CONFIG) -> "Settings":
        if not path.exists():
            log.warning("config_file_missing", path=str(path))
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log.error("config_file_read_failed", path=str(path), error=str(e))
            return cls()

        p = data.get("paths", {})
        h = data.get("hid", {})
        v = data.get("video", {})
        lg = data.get("logging", {})

        return cls(
            mediamtx_path=Path(p.get("mediamtx", "/opt/mediamtx")),
            edid_path=Path(p.get("edid", "/etc/kvm/force_720p.edid")),
            kvm_engine_bin=p.get("kvm_engine_bin", "kvm_engine"),
            video_device=v.get("device", "/dev/video0"),
            hid_port=h.get("port", 8080),
            jwt_secret=h.get("jwt_secret", ""),
            keyboard_device=h.get("keyboard_device", "/dev/hidg0"),
            mouse_device=h.get("mouse_device", "/dev/hidg1"),
            log_level=lg.get("level", "INFO"),
        )
