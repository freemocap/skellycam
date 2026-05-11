/*
 * SkellyCam C++ — 2-Camera Lockstep Sync
 *
 * Each camera runs on its own std::thread with a BoundedQueue (capacity 1)
 * providing structural backpressure. The gatherer (main thread) blocks on
 * recv() from all queues, creating an implicit barrier at every frame step.
 *
 * Architecture:
 *   Camera 0 thread ── [BoundedQueue(1)] ──┐
 *   Camera 1 thread ── [BoundedQueue(1)] ──┤
 *                                           ├── Gatherer (main thread)
 *                                           │    f0 = q0.recv()
 *                                           │    f1 = q1.recv()
 *                                           │    -- lockstep at step N --
 *                                           │    measure spread, report FPS
 */

#include <opencv2/opencv.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <queue>
#include <string>
#include <thread>
#include <vector>

// ===================================================================
// BoundedQueue<T> — thread-safe bounded queue with backpressure.
//
// send(item): blocks if the queue is full (capacity reached).
// recv():     blocks if the queue is empty, until an item is sent
//             or the queue is closed. Returns true on success.
// close():    unblocks all waiting threads; subsequent recv() returns false.
// ===================================================================
template <typename T> class BoundedQueue
{
  public:
    explicit BoundedQueue(size_t capacity = 1) : capacity_(capacity), closed_(false)
    {
    }

    // Block until there is space, then move the item into the queue.
    // Returns false if the queue was closed before space became available.
    bool send(T item)
    {
        std::unique_lock<std::mutex> lock(mutex_);
        not_full_.wait(lock, [this] { return queue_.size() < capacity_ || closed_; });
        if (closed_)
            return false;
        queue_.push(std::move(item));
        not_empty_.notify_one();
        return true;
    }

    // Block until an item is available, then move it out.
    // Returns false if the queue was closed and is empty.
    bool recv(T &out)
    {
        std::unique_lock<std::mutex> lock(mutex_);
        not_empty_.wait(lock, [this] { return !queue_.empty() || closed_; });
        if (queue_.empty())
            return false;
        out = std::move(queue_.front());
        queue_.pop();
        not_full_.notify_one();
        return true;
    }

    // Unblock all waiting threads. After close(), recv() returns false
    // and send() returns false once the queue drains.
    void close()
    {
        std::lock_guard<std::mutex> lock(mutex_);
        closed_ = true;
        not_empty_.notify_all();
        not_full_.notify_all();
    }

  private:
    std::queue<T> queue_;
    std::mutex mutex_;
    std::condition_variable not_full_;
    std::condition_variable not_empty_;
    size_t capacity_;
    bool closed_;
};

// ===================================================================
// CameraFrame — what each camera thread sends to the gatherer.
// ===================================================================
struct CameraFrame
{
    cv::Mat image;
    std::chrono::steady_clock::time_point grab_timestamp;
    long long frame_number;
};

// ===================================================================
// Camera thread — opens one camera, grabs frames, sends to queue.
// ===================================================================
namespace
{
    constexpr int k_target_width = 1280;
    constexpr int k_target_height = 720;
    constexpr int k_preferred_buffer_size = 1;
    constexpr int k_max_camera_open_retries = 5;

    std::string fourcc_to_string(int fourcc)
    {
        std::string result;
        result += static_cast<char>(fourcc & 0xFF);
        result += static_cast<char>((fourcc >> 8) & 0xFF);
        result += static_cast<char>((fourcc >> 16) & 0xFF);
        result += static_cast<char>((fourcc >> 24) & 0xFF);
        return result;
    }
}  // namespace

void camera_thread(int camera_index, BoundedQueue<CameraFrame> &queue,
                   std::atomic<bool> &shutdown)
{
    int mjpg_fourcc = cv::VideoWriter::fourcc('M', 'J', 'P', 'G');

    // -- Open --
    cv::VideoCapture camera;
    int attempts = 0;
    while (attempts < k_max_camera_open_retries && !camera.isOpened())
    {
        camera.open(camera_index, cv::CAP_DSHOW);
        attempts++;
    }
    if (!camera.isOpened())
    {
        std::cerr << "[Camera " << camera_index << "] FAILED to open\n";
        shutdown.store(true);
        queue.close();
        return;
    }

    camera.set(cv::CAP_PROP_FRAME_WIDTH, k_target_width);
    camera.set(cv::CAP_PROP_FRAME_HEIGHT, k_target_height);
    camera.set(cv::CAP_PROP_BUFFERSIZE, k_preferred_buffer_size);

    // First read starts the DirectShow stream
    cv::Mat test_frame;
    camera >> test_frame;
    if (test_frame.empty())
    {
        std::cerr << "[Camera " << camera_index << "] FAILED first read\n";
        shutdown.store(true);
        queue.close();
        return;
    }

    camera.set(cv::CAP_PROP_FOURCC, mjpg_fourcc);

    int actual_fourcc = static_cast<int>(camera.get(cv::CAP_PROP_FOURCC));
    std::cout << "[Camera " << camera_index << "] opened. "
              << "Backend=" << camera.getBackendName()
              << "  FOURCC=" << fourcc_to_string(actual_fourcc)
              << "  res=" << static_cast<int>(camera.get(cv::CAP_PROP_FRAME_WIDTH))
              << "x" << static_cast<int>(camera.get(cv::CAP_PROP_FRAME_HEIGHT))
              << "\n";

    // -- Grab loop --
    long long frame_number = 0;
    cv::Mat frame;

    while (!shutdown.load())
    {
        camera >> frame;
        if (frame.empty())
            continue;

        auto now = std::chrono::steady_clock::now();

        CameraFrame cf;
        cf.image = frame.clone();  // copy for the gatherer
        cf.grab_timestamp = now;
        cf.frame_number = frame_number++;

        if (!queue.send(std::move(cf)))
            break;  // queue closed, shutting down
    }

    camera.release();
    std::cout << "[Camera " << camera_index << "] stopped. "
              << frame_number << " frames grabbed.\n";
}

// ===================================================================
int main(int argument_count, char *argument_values[])
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    // Parse camera indices from command line
    std::vector<int> camera_indices;
    for (int i = 1; i < argument_count; ++i)
        camera_indices.push_back(std::stoi(argument_values[i]));
    if (camera_indices.empty())
        camera_indices = {0, 1};  // default: cameras 0 and 1

    const int camera_count = static_cast<int>(camera_indices.size());
    std::cout << "=== SkellyCam C++ Multi-Camera Lockstep ==="
              << "\nCameras: " << camera_count
              << "  |  indices: ";
    for (int idx : camera_indices)
        std::cout << idx << " ";
    std::cout << "\nResolution: " << k_target_width << "x" << k_target_height
              << "  |  MJPG  |  DSHOW\n\n";

    // -- Create queues + shutdown flag --
    // unique_ptr: BoundedQueue contains std::mutex, which is non-movable,
    // so we can't store queues directly in a std::vector (reallocation
    // attempts to move elements).
    std::atomic<bool> shutdown{false};
    std::vector<std::unique_ptr<BoundedQueue<CameraFrame>>> queues;
    std::vector<std::thread> threads;

    for (int i = 0; i < camera_count; ++i)
        queues.push_back(std::make_unique<BoundedQueue<CameraFrame>>(1));

    // -- Spawn camera threads --
    for (int i = 0; i < camera_count; ++i)
    {
        threads.emplace_back(camera_thread, camera_indices[i],
                             std::ref(*queues[i]), std::ref(shutdown));
    }

    // -- Gatherer loop --
    std::cout << "Gatherer running. Press Ctrl+C to stop.\n\n";

    long long step = 0;
    bool first_frame_arrived = false;
    auto fps_wall_start = std::chrono::steady_clock::now();  // set on first frame

    // FPS tracking: one interval counter shared across all cameras
    // (all cameras advance together in lockstep)
    long long report_steps = 0;
    long long total_steps = 0;
    auto report_interval_start = std::chrono::steady_clock::now();

    // Sync spread tracking for this report interval
    double interval_sum_spread_ms = 0.0;
    double interval_max_spread_ms = 0.0;
    double session_max_spread_ms = 0.0;

    while (!shutdown.load())
    {
        // Receive from ALL cameras — the implicit barrier
        std::vector<CameraFrame> frames;
        frames.reserve(camera_count);
        bool all_ok = true;
        for (int i = 0; i < camera_count; ++i)
        {
            CameraFrame cf;
            if (!queues[i]->recv(cf))
            {
                all_ok = false;
                break;
            }
            frames.push_back(std::move(cf));
        }
        if (!all_ok)
            break;

        // Set FPS baseline on first multiframe arrival
        if (!first_frame_arrived)
        {
            first_frame_arrived = true;
            fps_wall_start = std::chrono::steady_clock::now();
            report_interval_start = fps_wall_start;
        }

        step++;
        report_steps++;
        total_steps++;

        // Compute inter-camera timestamp spread for THIS multiframe
        double current_spread_ms = 0.0;
        if (camera_count >= 2)
        {
            long long min_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                                   frames[0].grab_timestamp.time_since_epoch())
                                   .count();
            long long max_ns = min_ns;
            for (int i = 1; i < camera_count; ++i)
            {
                long long ns =
                    std::chrono::duration_cast<std::chrono::nanoseconds>(
                        frames[i].grab_timestamp.time_since_epoch())
                        .count();
                if (ns < min_ns)
                    min_ns = ns;
                if (ns > max_ns)
                    max_ns = ns;
            }
            current_spread_ms =
                static_cast<double>(max_ns - min_ns) / 1'000'000.0;
            interval_sum_spread_ms += current_spread_ms;
            if (current_spread_ms > interval_max_spread_ms)
                interval_max_spread_ms = current_spread_ms;
            if (current_spread_ms > session_max_spread_ms)
                session_max_spread_ms = current_spread_ms;
        }

        // -- Print report every ~1 second --
        auto now = std::chrono::steady_clock::now();
        double interval_sec =
            std::chrono::duration<double>(now - report_interval_start).count();
        if (interval_sec >= 1.0)
        {
            double total_sec =
                std::chrono::duration<double>(now - fps_wall_start).count();
            double interval_fps = report_steps / interval_sec;
            double average_fps = total_steps / total_sec;
            double mean_spread = report_steps > 0
                                     ? interval_sum_spread_ms / report_steps
                                     : 0.0;

            // Build per-camera frame number string for debugging
            std::string frame_nums;
            for (int j = 0; j < camera_count; ++j)
            {
                frame_nums += " cam" + std::to_string(camera_indices[j]) + "="
                              + std::to_string(frames[j].frame_number);
            }

            std::cout << "Step " << step << frame_nums
                      << "  |  FPS: " << interval_fps << " (avg " << average_fps
                      << ")"
                      << "  |  sync spread (ms): cur=" << current_spread_ms
                      << "  mean=" << mean_spread
                      << "  max=" << interval_max_spread_ms
                      << "  |  elapsed: " << total_sec << " s" << std::endl;

            report_interval_start = now;
            report_steps = 0;
            interval_sum_spread_ms = 0.0;
            interval_max_spread_ms = 0.0;
        }

        // Auto-stop after ~10 seconds of frames for testing
        if (step >= 300)
        {
            std::cout << "\nReached 300 steps, stopping.\n";
            break;
        }
    }

    // -- Shutdown --
    std::cout << "\nShutting down...\n";
    shutdown.store(true);
    for (auto &q : queues)
        q->close();
    for (auto &t : threads)
    {
        if (t.joinable())
            t.join();
    }

    std::cout << "All camera threads joined. Done.\n";
    return EXIT_SUCCESS;
}
