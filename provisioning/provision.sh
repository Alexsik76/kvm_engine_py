#!/usr/bin/env bash
#
# provision.sh — turn a fresh Raspberry Pi OS (Pi 4 Model B) into a working
# autonomous KVM-over-IP device. Run as the project-owning user via sudo, in a
# system already prepared by Raspberry Pi Imager (user, hostname, SSH, locale).
#
#   sudo ./provision.sh              # run all steps
#   sudo ./provision.sh --dry-run    # print what WOULD happen, change nothing
#   sudo ./provision.sh 40_build     # run a single step by name
#
# Every step is idempotent: running twice must not break a working system.
# Nothing personal is hardcoded; deployment values come from provision.env or
# are autodetected.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate ourselves and the project root (repo is the parent of provisioning/).
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
STEPS_DIR="${SCRIPT_DIR}/steps"

# ---------------------------------------------------------------------------
# Must run as root (USB gadget configfs + apt + systemd need it), but we need
# the *real* login user, because the project lives in their home and the engine
# runs as that context. SUDO_USER is that user when invoked via sudo.
# ---------------------------------------------------------------------------
if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run with sudo (root needed for apt, boot config, USB gadget, systemd)." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Load parameters: provision.env if present, else defaults. Resolve the device
# user from SUDO_USER so we never bake a name in.
# ---------------------------------------------------------------------------
if [[ -f "${SCRIPT_DIR}/provision.env" ]]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/provision.env"
fi

KVM_DEVICE_USER="${KVM_DEVICE_USER:-${SUDO_USER:-}}"
if [[ -z "${KVM_DEVICE_USER}" || "${KVM_DEVICE_USER}" == "root" ]]; then
  echo "ERROR: cannot determine the device user. Run via 'sudo' as the project owner," >&2
  echo "       or set KVM_DEVICE_USER in provisioning/provision.env." >&2
  exit 1
fi
KVM_DEVICE_HOME="$(getent passwd "${KVM_DEVICE_USER}" | cut -d: -f6)"
if [[ -z "${KVM_DEVICE_HOME}" || ! -d "${KVM_DEVICE_HOME}" ]]; then
  echo "ERROR: home directory for user '${KVM_DEVICE_USER}' not found." >&2
  exit 1
fi

KVM_WEBRTC_IFACE="${KVM_WEBRTC_IFACE:-eth0}"
MEDIAMTX_VERSION="${MEDIAMTX_VERSION:-v1.16.2}"
NLOHMANN_JSON_VERSION="${NLOHMANN_JSON_VERSION:-v3.12.0}"

# Where the engine expects MediaMTX: settings.py uses project_root.parent/"mediamtx".
MEDIAMTX_DIR="$(cd "${PROJECT_ROOT}/.." && pwd)/mediamtx"

DRY_RUN=0
ONLY_STEP=""

for arg in "$@"; do
  case "${arg}" in
    --dry-run) DRY_RUN=1 ;;
    --help|-h)
      grep '^#' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' | head -20
      exit 0 ;;
    *) ONLY_STEP="${arg}" ;;
  esac
done

export PROJECT_ROOT STEPS_DIR KVM_DEVICE_USER KVM_DEVICE_HOME KVM_WEBRTC_IFACE \
       MEDIAMTX_VERSION NLOHMANN_JSON_VERSION MEDIAMTX_DIR DRY_RUN

# ---------------------------------------------------------------------------
# Shared helpers (sourced by steps). Kept tiny and predictable.
# ---------------------------------------------------------------------------
log()  { printf '\033[1;36m[provision]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[provision] WARN:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[provision] FATAL:\033[0m %s\n' "$*" >&2; exit 1; }

# run CMD...  — execute, or just print under --dry-run
run() {
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '\033[2m  would run:\033[0m %s\n' "$*"
  else
    "$@"
  fi
}

# ensure_line FILE LINE  — append LINE to FILE only if not already present.
# This is the safe pattern for editing config.txt etc.: never overwrite, only add.
ensure_line() {
  local file="$1" line="$2"
  if grep -qxF "${line}" "${file}" 2>/dev/null; then
    log "already present in $(basename "${file}"): ${line}"
  elif [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '\033[2m  would append to %s:\033[0m %s\n' "${file}" "${line}"
  else
    printf '%s\n' "${line}" >> "${file}"
    log "appended to $(basename "${file}"): ${line}"
  fi
}

export -f log warn die run ensure_line

# ---------------------------------------------------------------------------
# Run steps in order, or a single one if named.
# ---------------------------------------------------------------------------
log "device user : ${KVM_DEVICE_USER} (home ${KVM_DEVICE_HOME})"
log "project root: ${PROJECT_ROOT}"
log "mediamtx dir: ${MEDIAMTX_DIR}"
log "wired iface : ${KVM_WEBRTC_IFACE}"
[[ "${DRY_RUN}" -eq 1 ]] && warn "DRY RUN — no changes will be made."

mapfile -t ALL_STEPS < <(find "${STEPS_DIR}" -maxdepth 1 -name '[0-9]*.sh' | sort)

for step in "${ALL_STEPS[@]}"; do
  name="$(basename "${step}" .sh)"
  if [[ -n "${ONLY_STEP}" && "${name}" != "${ONLY_STEP}" ]]; then
    continue
  fi
  log "=== step ${name} ==="
  # shellcheck disable=SC1090
  source "${step}"
done

log "done."
[[ "${DRY_RUN}" -eq 1 ]] && warn "DRY RUN finished — re-run without --dry-run to apply."
exit 0
