/*
 * SkellyCam FOURCC Test Harness
 * Isolates the exact fix that makes MJPG + DSHOW work.
 *
 * Test modes (argv[2]):
 *   1 = pre-read FOURCC only
 *   2 = post-read FOURCC only (no pre-read set)
 *   3 = pre + post FOURCC (no exposure)
 *   4 = pre FOURCC + exposure (no post FOURCC)
 *   5 = full Python pattern: pre + post FOURCC + exposure
 *
 * Usage: skellycam_poc.exe <camera_index> <mode>
 */

#include <opencv2/opencv.hpp>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <string>

namespace
{
    constexpr int k_camera_api = cv::CAP_DSHOW;
    constexpr int k_target_width = 1280;
    constexpr int k_target_height = 720;
    constexpr int k_preferred_buffer_size = 1;
    constexpr int k_max_camera_open_retries = 5;
    constexpr int k_manual_exposure = 1;
    constexpr int k_target_exposure = -7;

    std::string fourcc_to_string(int fourcc)
    {
        std::string result;
        result += static_cast<char>(fourcc & 0xFF);
        result += static_cast<char>((fourcc >> 8) & 0xFF);
        result += static_cast<char>((fourcc >> 16) & 0xFF);
        result += static_cast<char>((fourcc >> 24) & 0xFF);
        return result;
    }

    void print_fourcc_check(const std::string &label, cv::VideoCapture &camera,
                            int requested)
    {
        int actual = static_cast<int>(camera.get(cv::CAP_PROP_FOURCC));
        int width = static_cast<int>(camera.get(cv::CAP_PROP_FRAME_WIDTH));
        int height = static_cast<int>(camera.get(cv::CAP_PROP_FRAME_HEIGHT));
        double fps = camera.get(cv::CAP_PROP_FPS);
        std::cout << "  [" << label << "]  FOURCC=" << fourcc_to_string(actual)
                  << "  res=" << width << "x" << height
                  << "  fps=" << fps << "\n";
    }

}  // namespace

int main(int argument_count, char *argument_values[])
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);

    int camera_index = 0;
    if (argument_count >= 2)
        camera_index = std::stoi(argument_values[1]);

    int mode = 5;
    if (argument_count >= 3)
        mode = std::stoi(argument_values[2]);

    const char *mode_label[] = {
        "",  // 0 unused
        "pre-read FOURCC only",
        "post-read FOURCC only",
        "pre+post FOURCC (no exposure)",
        "pre FOURCC + exposure (no post FOURCC)",
        "FULL Python pattern: pre+post FOURCC + exposure",
        "Mode 1 + CAP_PROP_FPS=30 (EXPECTED FAIL)",
        "Mode 5 + CAP_PROP_FPS=30 (full pattern but with FPS set)",
        "ORIGINAL BUG: burn frame BEFORE FOURCC set + FPS=30",
    };

    std::cout << "=== TEST MODE " << mode << ": " << mode_label[mode]
              << " ===\n\n";

    int mjpg_fourcc = cv::VideoWriter::fourcc('M', 'J', 'P', 'G');
    std::cout << "Requested FOURCC: " << fourcc_to_string(mjpg_fourcc)
              << " (0x" << std::hex << mjpg_fourcc << std::dec << ")\n\n";

    // ---- Open camera ----
    std::cout << "Opening camera " << camera_index
              << " with CAP_DSHOW...\n";
    cv::VideoCapture camera;
    int attempts = 0;
    while (attempts < k_max_camera_open_retries && !camera.isOpened())
    {
        if (attempts > 0)
            std::cerr << "  retry " << (attempts + 1) << "...\n";
        camera.open(camera_index, k_camera_api);
        attempts++;
    }
    if (!camera.isOpened())
    {
        std::cerr << "FAILED to open camera\n";
        return EXIT_FAILURE;
    }
    std::cout << "  opened OK\n";
    print_fourcc_check("after open", camera, mjpg_fourcc);

    cv::Mat frame;  // used by both standard flow and FPS check later
    bool set_fps = (mode == 6 || mode == 7 || mode == 8);
    bool mode_8_skip_standard_flow = false;
    constexpr int k_target_fps = 30;

    // ===========================================================
    // Mode 8: replicate the ORIGINAL FAILING sequence
    //   1. Set resolution + FPS  (DO NOT set FOURCC yet)
    //   2. Read burn frame (starts stream in YUY2 default)
    //   3. THEN set FOURCC to MJPG (after stream is already running)
    // This is the sequence from the very first DSHOW attempt.
    // ===========================================================
    if (mode == 8)
    {
        mode_8_skip_standard_flow = true;

        std::cout << "\n[Mode 8] Setting resolution+FPS (NO FOURCC yet)...\n";
        camera.set(cv::CAP_PROP_FRAME_WIDTH, k_target_width);
        camera.set(cv::CAP_PROP_FRAME_HEIGHT, k_target_height);
        camera.set(cv::CAP_PROP_FPS, k_target_fps);
        camera.set(cv::CAP_PROP_BUFFERSIZE, k_preferred_buffer_size);
        print_fourcc_check("after res+FPS (still no FOURCC)", camera, mjpg_fourcc);

        std::cout
            << "\n[Mode 8] Reading BURN FRAME (starts stream in YUY2)...\n";
        cv::Mat burn;
        camera >> burn;
        if (burn.empty())
        {
            std::cerr << "FAILED burn frame\n";
            return EXIT_FAILURE;
        }
        std::cout << "  burn frame OK  (size=" << burn.cols << "x" << burn.rows
                  << ")\n";
        print_fourcc_check("after burn frame (stream running in YUY2)", camera,
                           mjpg_fourcc);

        std::cout << "\n[Mode 8] NOW setting FOURCC to MJPG"
                  << " (stream is ALREADY running)...\n";
        camera.set(cv::CAP_PROP_FOURCC, mjpg_fourcc);
        print_fourcc_check("after FOURCC set (post-stream-start)", camera,
                           mjpg_fourcc);

        // read another frame to settle
        camera >> burn;
        print_fourcc_check("FINAL STATE", camera, mjpg_fourcc);
    }

    if (!mode_8_skip_standard_flow)
    {
    // ---- Step: set resolution (always done for modes 1-7) ----
    camera.set(cv::CAP_PROP_FRAME_WIDTH, k_target_width);
    camera.set(cv::CAP_PROP_FRAME_HEIGHT, k_target_height);
    if (set_fps)
        camera.set(cv::CAP_PROP_FPS, k_target_fps);
    camera.set(cv::CAP_PROP_BUFFERSIZE, k_preferred_buffer_size);

    // ---- Pre-read FOURCC set (all modes except 2) ----
    if (mode != 2)
    {
        std::cout << "\n[Pre-read] Setting FOURCC to MJPG...\n";
        camera.set(cv::CAP_PROP_FOURCC, mjpg_fourcc);
        print_fourcc_check("after pre-read FOURCC set", camera, mjpg_fourcc);
    }

    // ---- First read (always done) ----
    std::cout << "\n[First read] Starting DirectShow stream...\n";
    int read_attempts = 0;
    while (read_attempts < k_max_camera_open_retries)
    {
        camera >> frame;
        if (!frame.empty()) break;
        read_attempts++;
    }
    if (frame.empty())
    {
        std::cerr << "FAILED to read first frame\n";
        return EXIT_FAILURE;
    }
    std::cout << "  first frame OK  (size=" << frame.cols << "x"
              << frame.rows << ")\n";
    print_fourcc_check("after first read", camera, mjpg_fourcc);

    // ---- Exposure (modes 4, 5, 7) ----
    if (mode == 4 || mode == 5 || mode == 7)
    {
        std::cout << "\n[Post-read] Setting exposure to manual, value=-7...\n";
        camera.set(cv::CAP_PROP_AUTO_EXPOSURE, k_manual_exposure);
        camera.set(cv::CAP_PROP_EXPOSURE, k_target_exposure);
        print_fourcc_check("after exposure set", camera, mjpg_fourcc);
    }

    // ---- Re-set resolution post-read (modes 3, 5, 7) ----
    if (mode == 3 || mode == 5 || mode == 7)
    {
        std::cout << "\n[Post-read] Re-setting resolution...\n";
        camera.set(cv::CAP_PROP_FRAME_WIDTH, k_target_width);
        camera.set(cv::CAP_PROP_FRAME_HEIGHT, k_target_height);
        print_fourcc_check("after resolution re-set", camera, mjpg_fourcc);
    }

    // ---- Post-read FOURCC set (modes 2, 3, 5, 7) ----
    if (mode == 2 || mode == 3 || mode == 5 || mode == 7)
    {
        std::cout << "\n[Post-read] Setting FOURCC to MJPG...\n";
        camera.set(cv::CAP_PROP_FOURCC, mjpg_fourcc);
        print_fourcc_check("after post-read FOURCC set", camera, mjpg_fourcc);
    }

    // ---- Final re-read to lock in changes ----
    std::cout << "\n[Final read] Reading frame after all config...\n";
    camera >> frame;
    print_fourcc_check("FINAL STATE", camera, mjpg_fourcc);

    }  // end of if (!mode_8_skip_standard_flow)

    // ===============================================================
    // Verdict (common to all modes)
    // ===============================================================
    int final_fourcc = static_cast<int>(camera.get(cv::CAP_PROP_FOURCC));
    std::string final_str = fourcc_to_string(final_fourcc);
    bool mjpg_stuck = (final_str == "MJPG");

    std::cout << "\n========================================\n";
    std::cout << "VERDICT: FOURCC = " << final_str
              << "  ->  " << (mjpg_stuck ? "MJPG STUCK \xE2\x9C\x93" : "STILL YUY2 - FAILED")
              << "\n";
    std::cout << "========================================\n\n";

    if (!mjpg_stuck)
    {
        std::cout << "MJPG did NOT stick. Exiting without FPS test.\n";
        camera.release();
        return EXIT_FAILURE;
    }

    // ===============================================================
    // Quick FPS verification
    // ===============================================================
    long long total_count = 0;
    long long interval_count = 0;
    auto wall_start = std::chrono::steady_clock::now();
    auto rep_start = wall_start;

    std::cout << "Quick FPS check (5 seconds)...\n\n";
    while (total_count < 200)
    {
        camera >> frame;
        if (frame.empty()) continue;
        total_count++;
        interval_count++;

        auto now = std::chrono::steady_clock::now();
        double elapsed =
            std::chrono::duration<double>(now - rep_start).count();
        if (elapsed >= 1.0)
        {
            double total_elapsed =
                std::chrono::duration<double>(now - wall_start).count();
            std::cout << "  frame " << total_count
                      << "  |  interval: " << (interval_count / elapsed)
                      << " fps  |  average: " << (total_count / total_elapsed)
                      << " fps  |  time: " << total_elapsed << " s\n";
            rep_start = now;
            interval_count = 0;
        }
    }

    camera.release();
    return EXIT_SUCCESS;
}
