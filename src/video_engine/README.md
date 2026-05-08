# KVM Engine (C++ Video Encoder)

The `kvm_engine` is a high-performance, reactive C++ application responsible for capturing raw video frames from a hardware bridge (like the TC358743) and encoding them into an H.264 stream using hardware acceleration.

It is designed to run as a subprocess, outputting the encoded H.264 stream directly to `stdout`, where it is consumed by a streaming server like **MediaMTX**.

## Architecture

The engine is built around a non-blocking, event-driven loop using `poll()`. It achieves **zero-copy** video processing by sharing memory buffers between the capture device and the encoder device using Linux **DMABUF**.

### Core Components

*   **`main.cpp` (The Event Loop):**
    *   Initializes the devices and sets up signal handlers for graceful shutdown (`SIGINT`, `SIGTERM`).
    *   Uses `poll()` on the file descriptors of both the Capture and Encoder devices to react to available frames without busy-waiting.
    *   Pipes the final H.264 NAL units directly to `stdout`.
    *   Detects physical signal loss via `VIDIOC_QUERY_DV_TIMINGS`.

*   **`CaptureDevice` (V4L2 Capture):**
    *   Interfaces with the raw video input node (e.g., `/dev/video0`).
    *   Requests memory-mapped (MMAP) buffers.
    *   **Crucial:** Exports these buffers as DMABUF file descriptors (`exportBuffers()`), which allows other hardware blocks to read the memory without copying it through CPU RAM.

*   **`EncoderDevice` (V4L2 Memory-to-Memory Encoder):**
    *   Interfaces with the hardware H.264 encoder node (e.g., `/dev/video11`).
    *   **Input (OUTPUT queue):** Accepts raw frames from the `CaptureDevice`. It uses the `V4L2_MEMORY_DMABUF` mechanism, meaning it reads directly from the file descriptors exported by the capture device.
    *   **Output (CAPTURE queue):** Outputs compressed H.264 data into MMAP buffers, which the main loop reads and flushes to `stdout`.

*   **`Config`:**
    *   Loads and parses `config/config.json` using the `nlohmann/json` library.
    *   Handles translation of string configurations (like pixel formats or H.264 profiles) into V4L2-specific integer macros.

## Data Flow (Zero-Copy Pipeline)

1.  **Capture Ready:** `poll()` signals that the Capture device has a filled buffer.
2.  **Dequeue Capture:** Engine dequeues the filled raw frame buffer (`dequeueBuffer`).
3.  **Queue to Encoder:** Engine immediately queues this buffer to the Encoder using its DMABUF file descriptor (`queueOutputBuffer`). No data is copied.
4.  **Encoder Finished Reading:** Engine dequeues the raw buffer from the Encoder (`dequeueOutputBuffer`) and queues it back to the Capture device (`queueBuffer`) to be refilled.
5.  **Encode Ready:** `poll()` signals that the Encoder device has produced compressed data.
6.  **Output H.264:** Engine dequeues the compressed H.264 buffer (`dequeueCaptureBuffer`), writes the bytes to `stdout` (`std::fwrite`), and returns the empty buffer to the Encoder (`queueCaptureBuffer`).

## Error Handling

*   If the video signal is lost (e.g., target PC goes to sleep or changes resolution), `poll()` times out or returns `0`, and the engine queries `VIDIOC_QUERY_DV_TIMINGS`. If the signal is truly lost, the engine exits with code `1`. 
*   The Python orchestrator (`ServiceManager` / `MediaMTX`) detects this exit and handles restarting the engine when the signal returns.