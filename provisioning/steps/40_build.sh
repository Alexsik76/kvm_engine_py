# 40_build.sh — compile the C++ video engine.
#
# Mirrors app/services/builder.py EXACTLY (plain g++, no cmake):
#   g++ -O2 -mcpu=cortex-a72 -mtune=cortex-a72 -I <include> \
#       main.cpp CaptureDevice.cpp EncoderDevice.cpp Config.cpp -o kvm_engine
#
# The -mcpu=cortex-a72 flag pins this to the Pi 4. On other boards adjust the
# builder and this step together.
#
# The single-header dependency nlohmann/json is fetched the same way the builder
# does. Idempotent: skip if the binary already exists (use --force-build env to
# rebuild).

SRC="${PROJECT_ROOT}/src/video_engine"
INCLUDE="${SRC}/include"
JSON_HPP="${INCLUDE}/nlohmann/json.hpp"
JSON_URL="https://github.com/nlohmann/json/releases/download/${NLOHMANN_JSON_VERSION}/json.hpp"
ENGINE_BIN="${PROJECT_ROOT}/kvm_engine"

if [[ -x "${ENGINE_BIN}" && "${FORCE_BUILD:-0}" -ne 1 ]]; then
  log "engine binary already built (${ENGINE_BIN}); set FORCE_BUILD=1 to rebuild"
  return 0 2>/dev/null || exit 0
fi

# Fetch nlohmann/json header if missing.
if [[ ! -f "${JSON_HPP}" ]]; then
  log "fetching nlohmann/json ${NLOHMANN_JSON_VERSION}"
  run mkdir -p "$(dirname "${JSON_HPP}")"
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    printf '\033[2m  would download:\033[0m %s\n' "${JSON_URL}"
  else
    curl -fsSL "${JSON_URL}" -o "${JSON_HPP}" \
      || die "failed to download json.hpp from ${JSON_URL}"
  fi
else
  log "nlohmann/json header already present"
fi

log "compiling C++ engine -> ${ENGINE_BIN}"
run g++ -O2 -mcpu=cortex-a72 -mtune=cortex-a72 \
  -I "${INCLUDE}" \
  "${SRC}/main.cpp" "${SRC}/CaptureDevice.cpp" "${SRC}/EncoderDevice.cpp" "${SRC}/Config.cpp" \
  -o "${ENGINE_BIN}"

if [[ "${DRY_RUN}" -ne 1 ]]; then
  chown "${KVM_DEVICE_USER}:${KVM_DEVICE_USER}" "${ENGINE_BIN}"
  [[ -x "${ENGINE_BIN}" ]] || die "build reported success but ${ENGINE_BIN} is not executable"
fi

log "build step complete"
