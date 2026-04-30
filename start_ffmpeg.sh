#!/bin/bash

# Start the KVM engine and pipe raw H264 to FFmpeg.
# kvm_engine produces 60fps H264. Match input rate exactly (-r 60) and 
# regenerate PTS/DTS at the same 60fps base. Lower jitter, no slow-motion.
/home/alex/kvm_engine_py/kvm_engine | ffmpeg \
    -loglevel warning \
    -use_wallclock_as_timestamps 1 \
    -f h264 \
    -i pipe:0 \
    -c:v copy \
    -rtsp_transport tcp \
    -f rtsp \
    rtsp://admin:password@localhost:8554/kvm

# Non-obvious flags:
# -use_wallclock_as_timestamps: Use system time for sync
# -fflags +genpts: Generate missing time labels
# -rtsp_transport tcp: Force TCP for stable transfer
# -i pipe:0        -> Read input from the pipe (stdin)
# -c:v copy        -> Copy video data as is (no CPU usage)
# -fflags +genpts  -> Create timing data for each frame
