import os
import secrets
from pathlib import Path

def main():
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"

    lines = []
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    elif env_example.exists():
        with open(env_example, "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = [
            "KVM_DEVICE_USER=kvmowner\n",
            "KVM_DEVICE_HOST=kvm-ipi\n",
            "KVM_ACCESS_MODE=lan\n",
            "KVM_WEBRTC_UDP_PORT=30000\n",
            "KVM_ENABLE_STUN=false\n",
            "KVM_WEBRTC_IFACE=eth0\n",
            "KVM_RTSP_SERVER=127.0.0.1:8554\n",
            "KVM_JWT_SECRET=\n",
            "KVM_MEDIAMTX_PASS=\n"
        ]

    jwt_secret = secrets.token_hex(32)
    mediamtx_pass = secrets.token_hex(16)

    has_jwt = False
    has_pass = False
    updated_lines = []

    for line in lines:
        if line.startswith("KVM_JWT_SECRET="):
            parts = line.strip().split("=", 1)
            val = parts[1] if len(parts) > 1 else ""
            val = val.strip().strip('"').strip("'")
            if not val or val == "PLACEHOLDER_JWT_SECRET":
                line = f"KVM_JWT_SECRET={jwt_secret}\n"
            has_jwt = True
        elif line.startswith("KVM_MEDIAMTX_PASS="):
            parts = line.strip().split("=", 1)
            val = parts[1] if len(parts) > 1 else ""
            val = val.strip().strip('"').strip("'")
            if not val or val == "PLACEHOLDER_MTX_PASS":
                line = f"KVM_MEDIAMTX_PASS={mediamtx_pass}\n"
            has_pass = True
        updated_lines.append(line)

    if not has_jwt:
        updated_lines.append(f"KVM_JWT_SECRET={jwt_secret}\n")
    if not has_pass:
        updated_lines.append(f"KVM_MEDIAMTX_PASS={mediamtx_pass}\n")

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    print(f"Secrets generated/checked successfully and written to {env_file}")

if __name__ == "__main__":
    main()
