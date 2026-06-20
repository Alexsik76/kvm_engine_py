# 00_packages.sh — system packages needed to build and run the engine.
# Sourced by provision.sh (helpers: log/run/die already available).
#
# Rationale for each package (verified against the live working Pi):
#   build-essential : g++ toolchain — the C++ engine is built with a plain g++
#                     call (no cmake). Pulls in make, libc headers, etc.
#   git             : pull the repo / updates on the device.
#   python3-venv    : the orchestrator runs inside a venv.
#   ffmpeg          : remuxes the engine's H.264 into the RTSP loopback ingest.
#   v4l-utils       : v4l2-ctl, used for EDID and V4L2 inspection.
#
# NOT needed (confirmed): cmake, libavcodec-dev, libdrm-dev — the engine links
# only against libstdc++ and uses kernel V4L2/DMABUF headers already present.

PKGS=(build-essential git python3-venv ffmpeg v4l-utils)

log "ensuring apt packages: ${PKGS[*]}"

# Refresh once; cheap and avoids stale-index install failures on a fresh card.
run apt-get update -qq

# apt-get install is itself idempotent (already-installed packages are no-ops),
# so this is safe to re-run.
run env DEBIAN_FRONTEND=noninteractive apt-get install -y "${PKGS[@]}"

log "packages step complete"
