import json
from pathlib import Path
from typing import Optional
from pydantic import model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from jinja2 import Template

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="KVM_",
        extra="ignore"
    )

    device_user: str = "kvmowner"
    device_host: str = "kvm-ipi"

    project_root: Optional[Path] = None
    mediamtx_path: Optional[Path] = None
    edid_path: Optional[Path] = None
    kvm_engine_bin: str = "kvm_engine"

    hid_port: int = 8080
    jwt_secret: str = ""
    keyboard_device: str = "/dev/hidg0"
    mouse_device: str = "/dev/hidg1"

    video_device: str = "/dev/video0"

    log_level: str = "INFO"

    front_panel_enabled: bool = True
    front_panel_port: str = "/dev/ttyAMA0"
    front_panel_baudrate: int = 115200

    mediamtx_user: str = "kvm_user"
    mediamtx_pass: str = ""
    access_mode: str = "lan"
    public_host: str = ""
    webrtc_udp_port: int = 30000
    webrtc_additional_hosts: str = ""
    enable_stun: bool = False
    webrtc_iface: str = "eth0"
    rtsp_server: str = "127.0.0.1:8554"
    cors_allowed_origins: str = ""
    device_user_login: str = "kvm"
    device_password_hash: str = ""
    access_token_minutes: int = 30
    refresh_token_minutes: int = 10080
    node_id: str = "self"
    node_name: str = "kvm-ipi"
    stream_name: str = "kvm"
    has_front_panel: bool = True
    machine_info: Optional[dict] = None

    @field_validator("machine_info", mode="before")
    @classmethod
    def parse_machine_info(cls, v) -> Optional[dict]:
        if isinstance(v, str):
            if not v.strip():
                return None
            try:
                return json.loads(v)
            except Exception:
                return {"info": v}
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.cors_allowed_origins.strip():
            return []
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def compute_defaults(self) -> "Settings":
        if not self.project_root:
            self.project_root = Path(f"/home/{self.device_user}/kvm_engine_py")
        if not self.mediamtx_path:
            self.mediamtx_path = Path(f"/home/{self.device_user}/mediamtx")
        if not self.edid_path:
            self.edid_path = Path(f"/home/{self.device_user}/TC358743-Driver/720p60edid")
        return self

    def render_configs(self) -> None:
        config_dir = self.project_root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        example_file = config_dir / "config.json.example"
        config_file = config_dir / "config.json"
        
        if example_file.exists():
            with open(example_file, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        else:
            config_data = {
                "paths": {},
                "hid": {},
                "video": {},
                "logging": {}
            }

        if "paths" not in config_data:
            config_data["paths"] = {}
        config_data["paths"]["mediamtx"] = str(self.mediamtx_path)
        config_data["paths"]["edid"] = str(self.edid_path)
        config_data["paths"]["kvm_engine_bin"] = self.kvm_engine_bin

        if "hid" not in config_data:
            config_data["hid"] = {}
        config_data["hid"]["port"] = self.hid_port
        config_data["hid"]["jwt_secret"] = self.jwt_secret
        config_data["hid"]["keyboard_device"] = self.keyboard_device
        config_data["hid"]["mouse_device"] = self.mouse_device

        if "video" not in config_data:
            config_data["video"] = {}
        config_data["video"]["device"] = self.video_device

        if "logging" not in config_data:
            config_data["logging"] = {}
        config_data["logging"]["level"] = self.log_level

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)

        template_file = config_dir / "mediamtx.yml.j2"
        mediamtx_file = config_dir / "mediamtx.yml"
        
        if template_file.exists():
            with open(template_file, "r", encoding="utf-8") as f:
                template_content = f.read()
            
            template = Template(template_content)
            rendered_content = template.render(
                mediamtx_user=self.mediamtx_user,
                mediamtx_pass=self.mediamtx_pass,
                webrtc_additional_hosts=self.webrtc_additional_hosts,
                webrtc_udp_port=self.webrtc_udp_port,
                enable_stun=self.enable_stun,
                webrtc_iface=self.webrtc_iface,
                project_root=str(self.project_root)
            )
            
            with open(mediamtx_file, "w", encoding="utf-8") as f:
                f.write(rendered_content)
