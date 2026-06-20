#!/bin/bash

# Use environment variables passed from the orchestrator, with safe defaults.
PROJECT_ROOT="${KVM_PROJECT_ROOT:-/home/kvmowner/kvm_engine_py}"
MEDIAMTX_USER="${KVM_MEDIAMTX_USER:-kvm_user}"
MEDIAMTX_PASS="${KVM_MEDIAMTX_PASS:-kvm_pass}"
RTSP_SERVER="${KVM_RTSP_SERVER:-127.0.0.1:8554}"

cd "$PROJECT_ROOT" || exit 1

# Start the KVM engine and pipe raw H264 to FFmpeg.
./kvm_engine | ffmpeg \
    -loglevel warning \
    -f h264 \
    -r 60 \
    -i pipe:0 \
    -c:v copy \
    -bsf:v "setts=pts=N/60/TB:dts=N/60/TB" \
    -fflags +genpts \
    -rtsp_transport tcp \
    -f rtsp \
    rtsp://"$MEDIAMTX_USER":"$MEDIAMTX_PASS"@"$RTSP_SERVER"/kvm
