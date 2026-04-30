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
#ifdef DEBUG_TIMING
#include <chrono>
#include <algorithm>
#include <cmath>
#include <vector>
#endif

std::atomic<bool> keepRunning(true);

void signalHandler(int signum) {
    keepRunning = false;
}

#ifdef DEBUG_TIMING
struct TimingStats {
    std::vector<double> poll_ms, dqbuf_cap_ms, qbuf_out_us;
    std::vector<double> dqbuf_out_ms, dqbuf_enc_cap_ms, fwrite_us, iter_ms;
    int iter_count = 0;
    std::chrono::steady_clock::time_point window_start;

    TimingStats() : window_start(std::chrono::steady_clock::now()) {}

    void maybe_print() {
        double elapsed = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - window_start).count();
        if (elapsed < 1.0) return;

        auto avg_max = [](const std::vector<double>& v) -> std::pair<double, double> {
            if (v.empty()) return {0.0, 0.0};
            double sum = 0.0, mx = 0.0;
            for (double x : v) { sum += x; mx = std::max(mx, x); }
            return {sum / static_cast<double>(v.size()), mx};
        };

        std::pair<double,double> p  = avg_max(poll_ms);
        std::pair<double,double> c  = avg_max(dqbuf_cap_ms);
        std::pair<double,double> q  = avg_max(qbuf_out_us);
        std::pair<double,double> dqo = avg_max(dqbuf_out_ms);
        std::pair<double,double> dqc = avg_max(dqbuf_enc_cap_ms);
        std::pair<double,double> w  = avg_max(fwrite_us);
        std::pair<double,double> it = avg_max(iter_ms);

        std::fprintf(stderr,
            "[TIMING] iter=%d poll=%.1f/%.1f ms cap=%.1f/%.1f ms"
            " qbufO=%ld/%ld us dqbufO=%.1f/%.1f ms"
            " dqbufC=%.1f/%.1f ms write=%ld/%ld us total=%.1f/%.1f ms\n",
            iter_count,
            p.first,   p.second,
            c.first,   c.second,
            std::lround(q.first),   std::lround(q.second),
            dqo.first,  dqo.second,
            dqc.first,  dqc.second,
            std::lround(w.first),   std::lround(w.second),
            it.first,   it.second);

        poll_ms.clear(); dqbuf_cap_ms.clear(); qbuf_out_us.clear();
        dqbuf_out_ms.clear(); dqbuf_enc_cap_ms.clear(); fwrite_us.clear(); iter_ms.clear();
        iter_count = 0;
        window_start = std::chrono::steady_clock::now();
    }
};
#endif

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
    if (!capture.initialize(Config::data.buffers.count)) {
        std::cerr << "Fatal error: Failed to initialize capture device (no signal?)" << std::endl;
        return 1;
    }

    EncoderDevice encoder(Config::data.encoder.device);
    if (!encoder.initialize(capture.getWidth(), capture.getHeight(), Config::data.video.fps, Config::data.buffers.count)) {
        std::cerr << "Fatal error: Failed to initialize encoder device." << std::endl;
        return 1;
    }

    std::cerr << "KVM Engine v3.1 (Reactive) started." << std::endl;

    struct pollfd fds[2];
    fds[0].fd     = capture.getFd();
    fds[0].events = POLLIN;
    fds[1].fd     = encoder.getFd();
    fds[1].events = POLLIN;

#ifdef DEBUG_TIMING
    using clk = std::chrono::steady_clock;
    auto ms_since = [](clk::time_point t) {
        return std::chrono::duration<double, std::milli>(clk::now() - t).count();
    };
    auto us_since = [](clk::time_point t) {
        return std::chrono::duration<double, std::micro>(clk::now() - t).count();
    };
    TimingStats ts;
#endif

    try {
        while (keepRunning) {
#ifdef DEBUG_TIMING
            auto t0 = clk::now();
#endif
            int ret = poll(fds, 2, 5);
#ifdef DEBUG_TIMING
            ts.poll_ms.push_back(ms_since(t0));
#endif

            if (ret < 0) {
                if (errno == EINTR) continue;
                break;
            }

            if (ret == 0) {
                struct v4l2_dv_timings timings;
                if (ioctl(capture.getFd(), VIDIOC_QUERY_DV_TIMINGS, &timings) != 0) {
                    std::cerr << "Signal physically lost. Exiting for fallback..." << std::endl;
                    return 1;
                }
#ifdef DEBUG_TIMING
                ts.maybe_print();
#endif
                continue;
            }

            if (fds[0].revents & POLLIN) {
                uint32_t bytes_used = 0;
                struct timeval cap_ts = {};
#ifdef DEBUG_TIMING
                auto t0_dqbuf_cap = clk::now();
#endif
                int cap_idx = capture.dequeueBuffer(bytes_used, cap_ts);
#ifdef DEBUG_TIMING
                if (cap_idx != -1) ts.dqbuf_cap_ms.push_back(ms_since(t0_dqbuf_cap));
#endif
                if (cap_idx != -1) {
                    int dmabuf_fd = capture.getExportFd(cap_idx);
#ifdef DEBUG_TIMING
                    auto t0_qbuf = clk::now();
#endif
                    encoder.queueOutputBuffer(cap_idx, dmabuf_fd, bytes_used, cap_ts);
#ifdef DEBUG_TIMING
                    ts.qbuf_out_us.push_back(us_since(t0_qbuf));
#endif
                }
            }

#ifdef DEBUG_TIMING
            auto t0_dqbuf_out = clk::now();
#endif
            int enc_out_idx = encoder.dequeueOutputBuffer();
#ifdef DEBUG_TIMING
            ts.dqbuf_out_ms.push_back(ms_since(t0_dqbuf_out));
#endif
            if (enc_out_idx != -1) {
                capture.queueBuffer(enc_out_idx);
            }

            if (fds[1].revents & POLLIN) {
                uint32_t h264_bytes = 0;
                struct timeval enc_ts = {};
#ifdef DEBUG_TIMING
                auto t0_dqbuf_enc_cap = clk::now();
#endif
                int enc_cap_idx = encoder.dequeueCaptureBuffer(h264_bytes, enc_ts);
#ifdef DEBUG_TIMING
                if (enc_cap_idx != -1) ts.dqbuf_enc_cap_ms.push_back(ms_since(t0_dqbuf_enc_cap));
#endif
                if (enc_cap_idx != -1) {
                    void* frame_data = encoder.getCaptureBufferPointer(enc_cap_idx);
                    if (frame_data && h264_bytes > 0) {
#ifdef DEBUG_TIMING
                        auto t0_fwrite = clk::now();
#endif
                        std::fwrite(frame_data, 1, h264_bytes, stdout);
                        std::fflush(stdout);
#ifdef DEBUG_TIMING
                        ts.fwrite_us.push_back(us_since(t0_fwrite));
#endif
                    }
                    encoder.queueCaptureBuffer(enc_cap_idx);
                }
            }
#ifdef DEBUG_TIMING
            ts.iter_ms.push_back(ms_since(t0));
            ts.iter_count++;
            ts.maybe_print();
#endif
        }
    } catch (const std::exception& e) {
        std::cerr << "Runtime Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
