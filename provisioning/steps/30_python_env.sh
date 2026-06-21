# 30_python_env.sh — Python virtualenv + dependencies for the orchestrator.
#
# The engine is launched as root (USB gadget needs it) via .venv/bin/python, but
# the venv itself is owned by the device user so files in the repo stay theirs.
# We therefore create the venv and pip-install AS the device user.
#
# Idempotent: venv is reused if present; pip install is a no-op when satisfied.

VENV="${PROJECT_ROOT}/.venv"
REQ="${PROJECT_ROOT}/requirements.txt"

[[ -f "${REQ}" ]] || die "requirements.txt not found at ${REQ}"

if [[ ! -d "${VENV}" ]]; then
  log "creating venv at ${VENV}"
  run sudo -u "${KVM_DEVICE_USER}" python3 -m venv "${VENV}"
else
  log "venv already exists at ${VENV}"
fi

log "installing Python dependencies from requirements.txt"
run sudo -u "${KVM_DEVICE_USER}" "${VENV}/bin/python" -m pip install --upgrade pip
run sudo -u "${KVM_DEVICE_USER}" "${VENV}/bin/python" -m pip install -r "${REQ}"

log "python env step complete"
