# 20_mediamtx.sh — install the MediaMTX binary where the engine expects it.
# settings.py resolves mediamtx_path as project_root.parent/"mediamtx", so we
# install into ${MEDIAMTX_DIR} (computed in provision.sh).
#
# Idempotent: if the correct version is already installed, skip the download.

ARCH="linux_arm64"  # Pi 4 Model B
TARBALL="mediamtx_${MEDIAMTX_VERSION}_${ARCH}.tar.gz"
URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/${TARBALL}"
BIN="${MEDIAMTX_DIR}/mediamtx"

if [[ -x "${BIN}" ]] && "${BIN}" --version 2>/dev/null | grep -qx "${MEDIAMTX_VERSION}"; then
  log "MediaMTX ${MEDIAMTX_VERSION} already installed at ${BIN}"
  return 0 2>/dev/null || exit 0
fi

log "installing MediaMTX ${MEDIAMTX_VERSION} into ${MEDIAMTX_DIR}"
run mkdir -p "${MEDIAMTX_DIR}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '\033[2m  would download:\033[0m %s\n' "${URL}"
  printf '\033[2m  would extract mediamtx binary into:\033[0m %s\n' "${MEDIAMTX_DIR}"
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "${TMP}"' RETURN
  curl -fsSL "${URL}" -o "${TMP}/${TARBALL}" \
    || die "failed to download MediaMTX from ${URL} (no internet on the device?)"
  # The release tarball contains the binary plus a default mediamtx.yml; we only
  # take the binary — our config is rendered from the template by the engine.
  tar -xzf "${TMP}/${TARBALL}" -C "${MEDIAMTX_DIR}" mediamtx \
    || die "failed to extract mediamtx binary"
  chown "${KVM_DEVICE_USER}:${KVM_DEVICE_USER}" "${BIN}"
  chmod +x "${BIN}"
  log "MediaMTX installed: $("${BIN}" --version)"
fi

log "mediamtx step complete"
