# 60_service.sh — install and enable the kvm-engine systemd unit.
#
# Renders templates/kvm-engine.service.in with the real project root, installs
# to /etc/systemd/system, reloads systemd, and ENABLES the unit so it starts on
# boot. It does NOT start it now: boot-config/module changes from step 10 only
# take effect after a reboot, so the first real start must follow a reboot.
#
# Idempotent: re-rendering and re-enabling are safe.

TEMPLATE="${SCRIPT_DIR}/templates/kvm-engine.service.in"
UNIT="/etc/systemd/system/kvm-engine.service"

[[ -f "${TEMPLATE}" ]] || die "unit template not found at ${TEMPLATE}"

log "rendering systemd unit -> ${UNIT}"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '\033[2m  would render %s with PROJECT_ROOT=%s and write %s\033[0m\n' \
    "$(basename "${TEMPLATE}")" "${PROJECT_ROOT}" "${UNIT}"
else
  sed "s|__PROJECT_ROOT__|${PROJECT_ROOT}|g" "${TEMPLATE}" > "${UNIT}"
  chmod 0644 "${UNIT}"
fi

run systemctl daemon-reload
run systemctl enable kvm-engine.service

warn "Unit ENABLED but NOT started. Reboot to apply boot-config/modules, then:"
warn "  the engine starts automatically on boot, or: sudo systemctl start kvm-engine"
log "service step complete"
