/*
 * FOURCC Diagnostic: verify whether set(CAP_PROP_FOURCC) actually changes
 * the capture format, by measuring FPS (not just trusting get()).
 *
 * At 1280x720 over USB 2.0:
 *   YUY2 = ~55 MB/s uncompressed → ~10 fps max
 *   MJPG = ~3-6 MB/s compressed  → ~30 fps easily
 *
 * FPS measurement serves as independent ground truth for the pixel format.
 */

#include <opencv2/opencv.hpp>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>

namespace
{
    constexpr int k_camera_index = 0;
    constexpr int k_width = 1280;
    constexpr int k_height = 720;
    constexpr int k_fps_sample_frames = 60;
    constexpr int k_max_open_retries = 5;

    std::string fourcc_str(int v)
    {
        std::string s;
        s += static_cast<char>(v & 0xFF);
        s += static_cast<char>((v >> 8) & 0xFF);
        s += static_cast<char>((v >> 16) & 0xFF);
        s += static_cast<char>((v >> 24) & 0xFF);
        return s;
    }

    double measure_fps(cv::VideoCapture &camera)
    {
        cv::Mat frame;
        int count = 0;
        auto start = std::chrono::steady_clock::now();
        while (count < k_fps_sample_frames)
        {
            camera >> frame;
            if (frame.empty())
                continue;
            count++;
        }
        auto end = std::chrono::steady_clock::now();
        double elapsed =
            std::chrono::duration<double>(end - start).count();
        return count / elapsed;
    }

    void print_state(const char *label, cv::VideoCapture &camera)
    {
        int fourcc = static_cast<int>(camera.get(cv::CAP_PROP_FOURCC));
        int w = static_cast<int>(camera.get(cv::CAP_PROP_FRAME_WIDTH));
        int h = static_cast<int>(camera.get(cv::CAP_PROP_FRAME_HEIGHT));
        std::cout << "  [" << label << "]  "
                  << "get(FOURCC)=" << fourcc_str(fourcc)
                  << "  res=" << w << "x" << h << "\n";
    }
}  // namespace

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    int mjpg = cv::VideoWriter::fourcc('M', 'J', 'P', 'G');

    // ---- Open ----
    std::cout << "Opening camera " << k_camera_index
              << " with CAP_DSHOW...\n";
    cv::VideoCapture camera;
    int attempts = 0;
    while (attempts < k_max_open_retries && !camera.isOpened())
    {
        camera.open(k_camera_index, cv::CAP_DSHOW);
        attempts++;
    }
    if (!camera.isOpened())
    {
        std::cerr << "FAILED to open\n";
        return EXIT_FAILURE;
    }
    std::cout << "  opened OK\n";
    print_state("after open", camera);

    // ---- Set resolution (no FOURCC yet) ----
    camera.set(cv::CAP_PROP_FRAME_WIDTH, k_width);
    camera.set(cv::CAP_PROP_FRAME_HEIGHT, k_height);
    camera.set(cv::CAP_PROP_BUFFERSIZE, 1);

    // ================================================================
    // STAGE 1: Default format (no FOURCC set at all)
    // ================================================================
    std::cout << "\n=== STAGE 1: default format (no FOURCC set) ===\n";
    print_state("before first read", camera);

    double fps_default = measure_fps(camera);
    std::cout << "  measured FPS (first " << k_fps_sample_frames
              << " frames): " << fps_default << "\n";
    print_state("after first batch of reads", camera);

    // ================================================================
    // STAGE 2: Set FOURCC to MJPG (pre-read — but we already read)
    // ================================================================
    std::cout << "\n=== STAGE 2: setting FOURCC to MJPG "
              << "(stream has been running) ===\n";
    bool set_ok = camera.set(cv::CAP_PROP_FOURCC, mjpg);
    std::cout << "  set(CAP_PROP_FOURCC, MJPG) returned: "
              << (set_ok ? "true" : "false") << "\n";
    print_state("after set", camera);

    double fps_after_set = measure_fps(camera);
    std::cout << "  measured FPS (" << k_fps_sample_frames
              << " frames): " << fps_after_set << "\n";
    print_state("after second batch of reads", camera);

    // ================================================================
    // STAGE 3: Open fresh, set FOURCC BEFORE first read, then test
    // ================================================================
    std::cout << "\n=== STAGE 3: fresh open, set FOURCC BEFORE first read ===\n";
    camera.release();

    // Re-open
    camera.open(k_camera_index, cv::CAP_DSHOW);
    if (!camera.isOpened())
    {
        std::cerr << "FAILED to re-open\n";
        return EXIT_FAILURE;
    }
    camera.set(cv::CAP_PROP_FRAME_WIDTH, k_width);
    camera.set(cv::CAP_PROP_FRAME_HEIGHT, k_height);
    camera.set(cv::CAP_PROP_BUFFERSIZE, 1);

    print_state("after re-open (no FOURCC yet)", camera);
    set_ok = camera.set(cv::CAP_PROP_FOURCC, mjpg);
    std::cout << "  set(CAP_PROP_FOURCC, MJPG) returned: "
              << (set_ok ? "true" : "false") << "\n";
    print_state("after pre-read FOURCC set", camera);

    double fps_pre_set = measure_fps(camera);
    std::cout << "  measured FPS (" << k_fps_sample_frames
              << " frames): " << fps_pre_set << "\n";
    print_state("after first batch of reads", camera);

    // ================================================================
    // STAGE 4: Now set FOURCC again post-read on this same camera
    // ================================================================
    std::cout << "\n=== STAGE 4: set FOURCC again AFTER reads on same camera ===\n";
    set_ok = camera.set(cv::CAP_PROP_FOURCC, mjpg);
    std::cout << "  set(CAP_PROP_FOURCC, MJPG) returned: "
              << (set_ok ? "true" : "false") << "\n";
    print_state("after post-read set", camera);

    double fps_post_set = measure_fps(camera);
    std::cout << "  measured FPS (" << k_fps_sample_frames
              << " frames): " << fps_post_set << "\n";
    print_state("after final reads", camera);

    // ================================================================
    // Summary
    // ================================================================
    std::cout << "\n========================================\n";
    std::cout << "SUMMARY:\n";
    std::cout << "  Stage 1 (default, no FOURCC):       "
              << fps_default << " fps\n";
    std::cout << "  Stage 2 (post-read set):             "
              << fps_after_set << " fps\n";
    std::cout << "  Stage 3 (pre-read set, no post-set): "
              << fps_pre_set << " fps\n";
    std::cout << "  Stage 4 (pre-read set + post-set):   "
              << fps_post_set << " fps\n";
    std::cout << "========================================\n";

    camera.release();
    return EXIT_SUCCESS;
}
