#include "CaptureDevice.hpp"
#include "EncoderDevice.hpp"
#include "Config.hpp"
#include <iostream>
#include <poll.h>
#include <cstdio>
#include <unistd.h>
#include <csignal>
#include <atomic>
#include <filesystem>

std::atomic<bool> keepRunning(true);

void signalHandler(int signum) {
    keepRunning = false;
}

int main() {
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);

    std::filesystem::path exePath = std::filesystem::read_symlink("/proc/self/exe").parent_path();
    std::string configPath = (exePath / "config" / "config.json").string();
    if (!std::filesystem::exists(configPath)) {
        configPath = "./config/config.json";
    }

    try {
        Config::Loader::load(configPath);
    } catch (const std::exception& e) {
        std::cerr << "Failed to load config: " << e.what() << std::endl;
        return 1;
    }

    CaptureDevice capture(Config::data.video.device, Config::data.video.width, Config::data.video.height, Config::data.video.getV4L2Format());
    bool is_initialized = capture.initialize(Config::data.buffers.count);

    EncoderDevice encoder(Config::data.encoder.device);
    if (is_initialized) {
        encoder.initialize(capture.getWidth(), capture.getHeight(), Config::data.video.fps, Config::data.buffers.count);
    }

    std::cerr << "KVM Engine v2.7 (Smart Recovery) started." << std::endl;

    struct pollfd fds[2];
    int consecutive_timeouts = 0;

    try {
        while (keepRunning) {
            if (!is_initialized) {
                uint32_t w, h;
                if (capture.querySignal(w, h)) {
                    std::cerr << "Signal detected! Initializing hardware..." << std::endl;
                    if (capture.initialize(Config::data.buffers.count)) {
                        encoder.initialize(capture.getWidth(), capture.getHeight(), Config::data.video.fps, Config::data.buffers.count);
                        is_initialized = true;
                        consecutive_timeouts = 0;
                    }
                }
                if (!is_initialized) {
                    sleep(2);
                    continue;
                }
            }

            fds[0].fd     = capture.getFd();
            fds[0].events = POLLIN;
            fds[1].fd     = encoder.getFd();
            fds[1].events = POLLIN;

            int ret = poll(fds, 2, 1000);
            
            if (ret < 0) {
                if (errno == EINTR) continue; 
                break;
            }

            if (ret == 0) {
                consecutive_timeouts++;
                if (consecutive_timeouts % 5 == 0) {
                    uint32_t w, h;
                    if (!capture.querySignal(w, h)) {
                        std::cerr << "Signal lost. Entering standby mode..." << std::endl;
                        capture.stopStreaming();
                        capture.releaseBuffers();
                        is_initialized = false;
                    }
                }
                continue;
            }

            consecutive_timeouts = 0;

            if (fds[0].revents & POLLIN) {
                uint32_t bytes_used = 0;
                struct timeval cap_ts = {};
                int cap_idx = capture.dequeueBuffer(bytes_used, cap_ts);
                if (cap_idx != -1) {
                    int dmabuf_fd = capture.getExportFd(cap_idx);
                    encoder.queueOutputBuffer(cap_idx, dmabuf_fd, bytes_used, cap_ts);
                }
            }

            int enc_out_idx = encoder.dequeueOutputBuffer();
            if (enc_out_idx != -1) {
                capture.queueBuffer(enc_out_idx);
            }

            if (fds[1].revents & POLLIN) {
                uint32_t h264_bytes = 0;
                struct timeval enc_ts = {};
                int enc_cap_idx = encoder.dequeueCaptureBuffer(h264_bytes, enc_ts);
                if (enc_cap_idx != -1) {
                    void* frame_data = encoder.getCaptureBufferPointer(enc_cap_idx);
                    if (frame_data && h264_bytes > 0) {
                        std::fwrite(frame_data, 1, h264_bytes, stdout);
                        std::fflush(stdout);
                    }
                    encoder.queueCaptureBuffer(enc_cap_idx);
                }
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Runtime Error: " << e.what() << std::endl;
    }

    return 0;
}
