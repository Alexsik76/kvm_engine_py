# 10_boot_config.sh — firmware/boot configuration for capture, USB gadget, UART.
# Sourced by provision.sh (helpers: log/warn/run/ensure_line available).
#
# This is the most dangerous step: a corrupted config.txt makes the Pi
# unbootable. Therefore we NEVER overwrite config.txt — we only append missing
# lines via ensure_line (idempotent, grep-guarded). Re-running is a no-op.
#
# Every value mirrors the verified working Pi 4:
#   dtoverlay=tc358743            -> HDMI capture bridge (overlay ships with the OS)
#   dtoverlay=dwc2               -> USB gadget (HID keyboard/mouse via /dev/hidg*)
#   enable_uart=1 + disable-bt   -> frees /dev/ttyAMA0 for the RP2040 front panel
#   vc4-kms-v3d,cma-256 + gpu_mem=256 -> CMA/DMABUF memory for zero-copy video
#
# Changes here apply only AFTER a reboot.

# Bookworm+ keeps boot config under /boot/firmware; older images use /boot.
if [[ -f /boot/firmware/config.txt ]]; then
  CONFIG_TXT="/boot/firmware/config.txt"
elif [[ -f /boot/config.txt ]]; then
  CONFIG_TXT="/boot/config.txt"
else
  die "config.txt not found in /boot/firmware or /boot — unexpected OS layout."
fi
log "using boot config: ${CONFIG_TXT}"

# --- Safety: back up config.txt once, before touching it -------------------
BACKUP="${CONFIG_TXT}.kvm-backup"
if [[ ! -f "${BACKUP}" ]]; then
  run cp -a "${CONFIG_TXT}" "${BACKUP}"
  log "backed up original to ${BACKUP}"
else
  log "backup already exists: ${BACKUP}"
fi

# --- Required overlays / params (append only if missing) -------------------
# We add our lines under an [all] section. Raspberry Pi config.txt already has
# one; appending bare lines at EOF lands in the last-open section, which on the
# stock image is [all]. To be explicit and robust, we ensure a trailing [all].
ensure_line "${CONFIG_TXT}" "[all]"
ensure_line "${CONFIG_TXT}" "dtoverlay=tc358743"
ensure_line "${CONFIG_TXT}" "dtoverlay=dwc2"
ensure_line "${CONFIG_TXT}" "enable_uart=1"
ensure_line "${CONFIG_TXT}" "dtoverlay=disable-bt"
ensure_line "${CONFIG_TXT}" "gpu_mem=256"

# CMA: the stock image enables KMS with cma-256 already. We do NOT add a bare
# cma=... line (it conflicts with the vc4 overlay's cma-256). Only warn if the
# expected KMS+CMA line is absent, so the operator can check rather than us
# guessing and breaking video.
if ! grep -qE '^dtoverlay=vc4-kms-v3d,cma-256' "${CONFIG_TXT}"; then
  warn "Expected 'dtoverlay=vc4-kms-v3d,cma-256' not found in ${CONFIG_TXT}."
  warn "The stock Pi OS image sets this; verify CMA is sufficient for DMABUF."
fi

# --- Kernel modules for USB gadget (configfs composite device) -------------
# dwc2 alone is not enough; libcomposite is what exposes
# /sys/kernel/config/usb_gadget so the engine can build the HID gadget.
MODULES_FILE="/etc/modules-load.d/kvm-usb.conf"
if [[ -f "${MODULES_FILE}" ]] \
   && grep -qx dwc2 "${MODULES_FILE}" \
   && grep -qx libcomposite "${MODULES_FILE}"; then
  log "module-load file already correct: ${MODULES_FILE}"
elif [[ "${DRY_RUN}" -eq 1 ]]; then
  printf '\033[2m  would write %s with: dwc2, libcomposite\033[0m\n' "${MODULES_FILE}"
else
  printf 'dwc2\nlibcomposite\n' > "${MODULES_FILE}"
  log "wrote ${MODULES_FILE} (dwc2, libcomposite)"
fi

# --- Free the UART from the serial login console (RP2040 front panel) -------
# enable_uart=1 gives us the hardware UART, but Raspberry Pi OS still attaches a
# login console (serial-getty@ttyAMA0) to it by default. That getty keeps writing
# a login prompt into the RP2040 and competes with the engine for the port, so
# the front panel reports garbage ("unknown_command") and never shows PWR/HDD.
# mask is REQUIRED here: a plain disable is undone by a systemd generator that
# re-creates the instance on the next boot. Idempotent.
GETTY="serial-getty@ttyAMA0.service"
if [[ "$(systemctl is-enabled "${GETTY}" 2>/dev/null)" == "masked" ]]; then
  log "${GETTY} already masked (UART free for RP2040)"
else
  run systemctl stop "${GETTY}"
  run systemctl mask "${GETTY}"
  log "stopped + masked ${GETTY} (UART freed for RP2040)"
fi

warn "config.txt / modules changes take effect only AFTER a reboot."
log "boot config step complete"
