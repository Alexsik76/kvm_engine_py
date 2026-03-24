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
        width = timings.bt.width;
        height = timings.bt.height;
        std::cerr << "Signal detected: " << width << "x" << height << std::endl;
    } else {
        std::cerr << "No HDMI signal detected." << std::endl;
        return false;
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
