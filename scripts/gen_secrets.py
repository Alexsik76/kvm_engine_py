import os
import secrets
import getpass
import sys
import bcrypt
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
            "KVM_MEDIAMTX_PASS=\n",
            "KVM_DEVICE_USER_LOGIN=kvm\n",
            "KVM_DEVICE_PASSWORD_HASH=\n"
        ]

    jwt_secret = secrets.token_hex(32)
    mediamtx_pass = secrets.token_hex(16)

    existing_secrets = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key, val = line.strip().split("=", 1)
            val = val.strip().strip('"').strip("'")
            existing_secrets[key] = val

    pwd_hash = existing_secrets.get("KVM_DEVICE_PASSWORD_HASH", "")
    if not pwd_hash:
        init_password = os.environ.get("KVM_INIT_PASSWORD")
        if not init_password:
            if sys.stdin.isatty():
                init_password = getpass.getpass("Enter KVM password (will be hashed): ")
            else:
                init_password = secrets.token_urlsafe(12)
                print(f"No password provided (KVM_INIT_PASSWORD not set). Generated temporary password: {init_password}")
        
        hashed = bcrypt.hashpw(init_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        pwd_hash = hashed

    has_jwt = False
    has_pass = False
    has_user_login = False
    has_pwd_hash = False
    updated_lines = []

    for line in lines:
        if line.startswith("KVM_JWT_SECRET="):
            val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            if not val or val == "PLACEHOLDER_JWT_SECRET":
                line = f"KVM_JWT_SECRET={jwt_secret}\n"
            has_jwt = True
        elif line.startswith("KVM_MEDIAMTX_PASS="):
            val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            if not val or val == "PLACEHOLDER_MTX_PASS":
                line = f"KVM_MEDIAMTX_PASS={mediamtx_pass}\n"
            has_pass = True
        elif line.startswith("KVM_DEVICE_USER_LOGIN="):
            has_user_login = True
        elif line.startswith("KVM_DEVICE_PASSWORD_HASH="):
            val = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
            if not val:
                line = f"KVM_DEVICE_PASSWORD_HASH={pwd_hash}\n"
            has_pwd_hash = True
        updated_lines.append(line)

    if not has_jwt:
        updated_lines.append(f"KVM_JWT_SECRET={jwt_secret}\n")
    if not has_pass:
        updated_lines.append(f"KVM_MEDIAMTX_PASS={mediamtx_pass}\n")
    if not has_user_login:
        updated_lines.append("KVM_DEVICE_USER_LOGIN=kvm\n")
    if not has_pwd_hash:
        updated_lines.append(f"KVM_DEVICE_PASSWORD_HASH={pwd_hash}\n")

    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    print(f"Secrets generated/checked successfully and written to {env_file}")

if __name__ == "__main__":
    main()
