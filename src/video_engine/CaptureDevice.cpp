#include "CaptureDevice.hpp"
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <iostream>
#include <sys/mman.h>
#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <linux/videodev2.h>

CaptureDevice::CaptureDevice(const std::string& path, uint32_t w, uint32_t h, uint32_t format)
    : devicePath(path), fd(-1), width(w), height(h), pixelFormat(format) {}

CaptureDevice::~CaptureDevice() {
    if (fd != -1) {
        int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        ioctl(fd, VIDIOC_STREAMOFF, &type);
        for (auto& buf : buffers) {
            munmap(buf.start, buf.length);
            if (buf.export_fd != -1) close(buf.export_fd);
        }
        close(fd);
    }
}

bool CaptureDevice::openDevice() {
    fd = open(devicePath.c_str(), O_RDWR | O_NONBLOCK, 0);
    return (fd != -1);
}

bool CaptureDevice::configureFormat() {
    struct v4l2_dv_timings timings;
    if (ioctl(fd, VIDIOC_QUERY_DV_TIMINGS, &timings) == 0) {
        if (ioctl(fd, VIDIOC_S_DV_TIMINGS, &timings) != -1) {
            width = timings.bt.width;
            height = timings.bt.height;
            std::cerr << "Signal detected and applied: " << width << "x" << height << std::endl;
        }
    } else {
        std::cerr << "No HDMI signal detected on startup. Using default fallback resolution: " 
                  << width << "x" << height << std::endl;
    }

    struct v4l2_format fmt = {};
    fmt.type               = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width      = width;
    fmt.fmt.pix.height     = height;
    fmt.fmt.pix.pixelformat = pixelFormat;
    fmt.fmt.pix.field      = V4L2_FIELD_NONE;

    if (ioctl(fd, VIDIOC_S_FMT, &fmt) == -1) return false;
    
    width = fmt.fmt.pix.width;
    height = fmt.fmt.pix.height;
    return true;
}

void CaptureDevice::fillBufferWithBlack(int index) {
    if (index < 0 || (size_t)index >= buffers.size()) return;
    
    uint32_t* ptr = static_cast<uint32_t*>(buffers[index].start);
    size_t words = buffers[index].length / 4;
    
    // 1. Draw SMPTE Color Bars background
    const uint32_t COLOR_BARS[8] = {
        0x80eb80eb, // White
        0x10d292d2, // Yellow
        0xa6aa10aa, // Cyan
        0x36912291, // Green
        0xca51dd51, // Magenta
        0x5a3fef3f, // Red
        0xf01c6e1c, // Blue
        0x80108010  // Black
    };

    uint32_t words_per_row = width / 2;
    uint32_t bar_width_words = words_per_row / 8;
    if (bar_width_words == 0) bar_width_words = 1;

    for (size_t row = 0; row < height; ++row) {
        size_t row_offset = row * words_per_row;
        if (row_offset + words_per_row > words) break; 
        for (size_t col = 0; col < words_per_row; ++col) {
            int bar_index = col / bar_width_words;
            if (bar_index > 7) bar_index = 7;
            ptr[row_offset + col] = COLOR_BARS[bar_index];
        }
    }

    // 2. Draw "NO SIGNAL" Text overlay
    const char* text[5] = {
        "N   N  OOO       SSS  III  GGG  N   N   A   L    ",
        "NN  N O   O     S      I  G     NN  N  A A  L    ",
        "N N N O   O      SSS   I  G  GG N N N AAAAA L    ",
        "N  NN O   O         S  I  G   G N  NN A   A L    ",
        "N   N  OOO       SSS  III  GGG  N   N A   A LLLLL"
    };
    
    int scale = (width >= 1280) ? 16 : 8; // Pixel scale multiplier
    int text_w = 49 * scale;
    int text_h = 5 * scale;
    
    // Center coordinates (ensure start_x is even for UYVY alignment)
    int start_x = ((width - text_w) / 2) & ~1;
    int start_y = (height - text_h) / 2;
    
    // Draw a black background box for the text
    int padding = 2 * scale;
    int box_start_x = (start_x - padding) & ~1;
    int box_start_y = start_y - padding;
    int box_w = text_w + 2 * padding;
    int box_h = text_h + 2 * padding;
    
    uint32_t black_color = 0x80108010;
    uint32_t white_color = 0x80eb80eb;

    // Draw Box
    for (int y = box_start_y; y < box_start_y + box_h; ++y) {
        if (y < 0 || y >= (int)height) continue;
        size_t row_offset = y * words_per_row;
        for (int x = box_start_x; x < box_start_x + box_w; x += 2) {
            if (x < 0 || x >= (int)width) continue;
            size_t offset = row_offset + (x / 2);
            if (offset < words) ptr[offset] = black_color;
        }
    }

    // Draw Text
    for (int ty = 0; ty < 5; ++ty) {
        for (int tx = 0; tx < 49; ++tx) {
            if (text[ty][tx] != ' ') {
                for (int dy = 0; dy < scale; ++dy) {
                    for (int dx = 0; dx < scale; dx += 2) {
                        int px = start_x + tx * scale + dx;
                        int py = start_y + ty * scale + dy;
                        if (px >= 0 && px < (int)width && py >= 0 && py < (int)height) {
                            size_t offset = py * words_per_row + (px / 2);
                            if (offset < words) ptr[offset] = white_color;
                        }
                    }
                }
            }
        }
    }
}

bool CaptureDevice::requestBuffers(uint32_t count) {
    struct v4l2_requestbuffers req = {};
    req.count  = count;
    req.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;
    return (ioctl(fd, VIDIOC_REQBUFS, &req) != -1);
}

bool CaptureDevice::mapAndQueueBuffers(uint32_t count) {
    for (uint32_t i = 0; i < count; ++i) {
        struct v4l2_buffer buf = {};
        buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index  = i;

        if (ioctl(fd, VIDIOC_QUERYBUF, &buf) == -1) return false;

        Buffer buffer;
        buffer.length    = buf.length;
        buffer.start     = mmap(NULL, buf.length, PROT_READ | PROT_WRITE, MAP_SHARED, fd, buf.m.offset);
        buffer.export_fd = -1;
        if (buffer.start == MAP_FAILED) return false;

        buffers.push_back(buffer);
        if (ioctl(fd, VIDIOC_QBUF, &buf) == -1) return false;
    }
    return true;
}

bool CaptureDevice::exportBuffers() {
    for (size_t i = 0; i < buffers.size(); ++i) {
        struct v4l2_exportbuffer expbuf = {};
        expbuf.type  = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        expbuf.index = i;
        if (ioctl(fd, VIDIOC_EXPBUF, &expbuf) == -1) return false;
        buffers[i].export_fd = expbuf.fd;
    }
    return true;
}

bool CaptureDevice::startStreaming() {
    int type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    return (ioctl(fd, VIDIOC_STREAMON, &type) != -1);
}

bool CaptureDevice::initialize(uint32_t count) {
    if (!openDevice()) return false;
    if (!configureFormat()) return false;
    if (!requestBuffers(count)) return false;
    if (!mapAndQueueBuffers(count)) return false;
    if (!exportBuffers()) return false;
    if (!startStreaming()) return false;
    return true;
}

int CaptureDevice::dequeueBuffer(uint32_t& bytes_used, struct timeval& timestamp) {
    struct v4l2_buffer buf = {};
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    if (ioctl(fd, VIDIOC_DQBUF, &buf) == -1) return -1;
    bytes_used = buf.bytesused;
    timestamp  = buf.timestamp;
    return buf.index;
}

bool CaptureDevice::queueBuffer(int index) {
    struct v4l2_buffer buf = {};
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index  = index;
    return (ioctl(fd, VIDIOC_QBUF, &buf) != -1);
}

int CaptureDevice::getExportFd(size_t index) const {
    return (index < buffers.size()) ? buffers[index].export_fd : -1;
}

int CaptureDevice::getFd() const { return fd; }
