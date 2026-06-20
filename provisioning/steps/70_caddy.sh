# 70_caddy.sh — install Caddy and serve the SPA single-origin.
#
# Caddy serves the pre-built SPA (vendored in the repo at web/) on :80 and proxies
# /api and /ws to the engine on 127.0.0.1:8080. The SPA is NOT built here — it is
# committed into the repo (built on a workstation with an empty VITE_API_BASE_URL
# so all calls are relative). No Node.js on the device.
#
# Self-contained defaults (override in provision.env if needed):
CADDY_VERSION="${CADDY_VERSION:-v2.11.4}"
CADDY_USER="${CADDY_USER:-${KVM_DEVICE_USER}}"

WEB_ROOT="${PROJECT_ROOT}/web"
CADDY_BIN="/usr/local/bin/caddy"
CADDYFILE="/etc/caddy/Caddyfile"
UNIT="/etc/systemd/system/caddy.service"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"

# --- Sanity: the vendored SPA must be present ------------------------------
if [[ ! -f "${WEB_ROOT}/index.html" ]]; then
  warn "No SPA found at ${WEB_ROOT}/index.html."
  warn "Build the frontend on a workstation with an EMPTY VITE_API_BASE_URL and commit"
  warn "the dist output into ${PROJECT_ROOT}/web/ before provisioning. Skipping Caddy."
  return 0 2>/dev/null || exit 0
fi

# --- Install the Caddy static binary (idempotent) --------------------------
ARCH="linux_arm64"
VER_NO_V="${CADDY_VERSION#v}"
TARBALL="caddy_${VER_NO_V}_${ARCH}.tar.gz"
URL="https://github.com/caddyserver/caddy/releases/download/${CADDY_VERSION}/${TARBALL}"

if [[ -x "${CADDY_BIN}" ]] && "${CADDY_BIN}" version 2>/dev/null | grep -q "${VER_NO_V}"; then
  log "Caddy ${CADDY_VERSION} already installed"
else
  log "installing Caddy ${CADDY_VERSION}"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '\033[2m  would download:\033[0m %s\n' "${URL}"
    printf '\033[2m  would install caddy binary to:\033[0m %s\n' "${CADDY_BIN}"
  else
    TMP="$(mktemp -d)"; trap 'rm -rf "${TMP}"' RETURN
    curl -fsSL "${URL}" -o "${TMP}/${TARBALL}" \
      || die "failed to download Caddy from ${URL}"
    tar -xzf "${TMP}/${TARBALL}" -C "${TMP}" caddy || die "failed to extract caddy"
    install -m 0755 "${TMP}/caddy" "${CADDY_BIN}"
    log "Caddy installed: $("${CADDY_BIN}" version | head -1)"
  fi
fi

# --- Render Caddyfile -------------------------------------------------------
log "rendering ${CADDYFILE} (web root: ${WEB_ROOT})"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '\033[2m  would write %s proxying /api,/ws -> 127.0.0.1:8080, static from %s\033[0m\n' \
    "${CADDYFILE}" "${WEB_ROOT}"
else
  mkdir -p /etc/caddy
  sed "s|__WEB_ROOT__|${WEB_ROOT}|g" "${TEMPLATE_DIR}/Caddyfile.in" > "${CADDYFILE}"
  # Validate before activating — a bad Caddyfile must not get enabled.
  "${CADDY_BIN}" validate --config "${CADDYFILE}" \
    || die "Caddyfile failed validation; not installing the service"
fi

# --- Render + install systemd unit -----------------------------------------
log "rendering ${UNIT} (user: ${CADDY_USER})"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '\033[2m  would write %s and enable+start caddy\033[0m\n' "${UNIT}"
else
  sed "s|__CADDY_USER__|${CADDY_USER}|g" "${TEMPLATE_DIR}/caddy.service.in" > "${UNIT}"
  chmod 0644 "${UNIT}"
fi

run systemctl daemon-reload
run systemctl enable caddy.service
# Caddy is independent of the boot-config/module reboot, so starting now is safe
# and lets you reach the SPA at http://<host>.lan immediately.
run systemctl restart caddy.service

log "caddy step complete — SPA on http://<host>/ , API/WS proxied to the engine"
