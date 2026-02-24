// src/services/server/server-helpers/display-framerate-tracker.ts
//
// Tracks the rate at which decoded frames are dispatched to canvas workers
// on the frontend. Uses a rolling window of inter-frame durations measured
// via performance.now() at the moment frames are actually processed.

import { DetailedFramerate } from "@/services/server/server-helpers/framerate-store";

const DEFAULT_WINDOW_SIZE = 200;

/**
 * Measures the true display framerate by recording timestamps each time
 * a decoded frame batch is dispatched to canvas rendering workers.
 *
 * Maintains a fixed-capacity ring buffer of inter-frame durations and
 * computes statistics on demand.
 */
export class DisplayFramerateTracker {
    private readonly _maxDurations: number;
    private readonly _durations: Float64Array;
    private _writeIndex: number = 0;
    private _count: number = 0;
    private _lastTimestamp: number | null = null;
    private _lastDurationMs: number | null = null;

    constructor(windowSize: number = DEFAULT_WINDOW_SIZE) {
        this._maxDurations = windowSize;
        this._durations = new Float64Array(windowSize);
    }

    /**
     * Record a frame dispatch event. Call this each time a decoded frame
     * batch is sent to the canvas workers.
     */
    stamp(): void {
        const now = performance.now();
        if (this._lastTimestamp !== null) {
            const durationMs = now - this._lastTimestamp;
            this._durations[this._writeIndex] = durationMs;
            this._writeIndex = (this._writeIndex + 1) % this._maxDurations;
            if (this._count < this._maxDurations) {
                this._count++;
            }
            this._lastDurationMs = durationMs;
        }
        this._lastTimestamp = now;
    }

    /**
     * The most recent individual inter-frame duration in milliseconds,
     * or null if fewer than 2 stamps have been recorded.
     */
    get lastDurationMs(): number | null {
        return this._lastDurationMs;
    }

    get hasData(): boolean {
        return this._count >= 1;
    }

    /**
     * Compute a DetailedFramerate snapshot from the current rolling window.
     * Returns null if no durations have been recorded yet.
     */
    computeFramerate(): DetailedFramerate | null {
        if (this._count === 0) return null;

        // Extract the valid durations into a contiguous array for stats
        const n = this._count;
        const values = new Float64Array(n);
        if (n < this._maxDurations) {
            // Buffer hasn't wrapped yet — values are [0..n)
            values.set(this._durations.subarray(0, n));
        } else {
            // Buffer has wrapped — read from writeIndex (oldest) forward
            for (let i = 0; i < n; i++) {
                values[i] = this._durations[(this._writeIndex + i) % this._maxDurations];
            }
        }

        // Compute statistics
        let sum = 0;
        let min = Infinity;
        let max = -Infinity;
        for (let i = 0; i < n; i++) {
            const v = values[i];
            sum += v;
            if (v < min) min = v;
            if (v > max) max = v;
        }
        const mean = sum / n;

        // Variance (population)
        let m2 = 0;
        for (let i = 0; i < n; i++) {
            const d = values[i] - mean;
            m2 += d * d;
        }
        const variance = n > 1 ? m2 / n : 0;
        const stddev = Math.sqrt(variance);
        const cv = mean > 0 ? stddev / mean : 0;

        // Median via sort (values is a copy so sorting is safe)
        values.sort();
        const median = n % 2 === 0
            ? (values[n / 2 - 1] + values[n / 2]) / 2
            : values[Math.floor(n / 2)];

        return {
            mean_frame_duration_ms: mean,
            mean_frames_per_second: mean > 0 ? 1000 / mean : 0,
            frame_duration_mean: mean,
            frame_duration_median: median,
            frame_duration_min: min,
            frame_duration_max: max,
            frame_duration_stddev: stddev,
            frame_duration_coefficient_of_variation: cv,
            calculation_window_size: n,
            framerate_source: "Display",
        };
    }

    clear(): void {
        this._writeIndex = 0;
        this._count = 0;
        this._lastTimestamp = null;
        this._lastDurationMs = null;
    }
}
