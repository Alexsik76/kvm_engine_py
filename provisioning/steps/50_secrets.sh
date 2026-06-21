# 50_secrets.sh — create .env and generate secrets (incl. the device password).
#
# .env is the single source of truth and is git-ignored. We create it from the
# committed .env.example if absent, set deploy-specific values, then run
# gen_secrets.py which (idempotently) fills JWT secret, MediaMTX password, and
# PROMPTS for the device login password if its hash is not yet set.
#
# This step is INTERACTIVE (password prompt). It cannot be fully unattended,
# by design — we never ship a default password.

ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"
GEN="${PROJECT_ROOT}/scripts/gen_secrets.py"
VENV_PY="${PROJECT_ROOT}/.venv/bin/python"

[[ -f "${ENV_EXAMPLE}" ]] || die ".env.example not found at ${ENV_EXAMPLE}"
[[ -f "${GEN}" ]]         || die "scripts/gen_secrets.py not found"

# Create .env from example only if it does not exist (never clobber a real one).
if [[ ! -f "${ENV_FILE}" ]]; then
  log "creating .env from .env.example"
  run sudo -u "${KVM_DEVICE_USER}" cp "${ENV_EXAMPLE}" "${ENV_FILE}"
else
  log ".env already exists — leaving it in place"
fi

# Set the wired interface for WebRTC ICE (idempotent in-place edit).
set_env_kv() {
  local key="$1" val="$2"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '\033[2m  would set %s=%s in .env\033[0m\n' "${key}" "${val}"
    return
  fi
  if grep -qE "^${key}=" "${ENV_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "${ENV_FILE}"
  elif grep -qE "^# *${key}=" "${ENV_FILE}"; then
    sed -i "s|^# *${key}=.*|${key}=${val}|" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${val}" >> "${ENV_FILE}"
  fi
  chown "${KVM_DEVICE_USER}:${KVM_DEVICE_USER}" "${ENV_FILE}"
}

set_env_kv "KVM_WEBRTC_IFACE" "${KVM_WEBRTC_IFACE}"

# Generate secrets + (interactively) the device password. gen_secrets.py is
# idempotent: existing secrets are kept, only missing ones are created.
log "generating secrets (will prompt for the device password if unset)"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '\033[2m  would run:\033[0m %s scripts/gen_secrets.py (interactive)\n' "${VENV_PY}"
else
  sudo -u "${KVM_DEVICE_USER}" "${VENV_PY}" "${GEN}"
fi

log "secrets step complete"
