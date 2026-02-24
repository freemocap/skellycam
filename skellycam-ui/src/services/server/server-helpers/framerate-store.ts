// src/services/server/server-helpers/framerate-store.ts

const MAX_DURATION_HISTORY = 1000;

/** Matches the shape sent by the Python backend's CurrentFramerate.model_dump() */
export type DetailedFramerate = {
    mean_frame_duration_ms: number;
    mean_frames_per_second: number;
    frame_duration_max: number;
    frame_duration_min: number;
    frame_duration_mean: number;
    frame_duration_stddev: number;
    frame_duration_median: number;
    frame_duration_coefficient_of_variation: number;
    calculation_window_size: number;
    framerate_source: string;
};

/** A single data point with the real timestamp of when it was recorded. */
export type TimestampedSample = {
    timestamp: number;
    value: number;
};

/** Snapshot of all framerate data, returned by getSnapshot(). */
export type FramerateSnapshot = {
    currentBackendFramerate: DetailedFramerate | null;
    currentFrontendFramerate: DetailedFramerate | null;
    aggregateBackendFramerate: DetailedFramerate | null;
    aggregateFrontendFramerate: DetailedFramerate | null;
    recentFrontendDurations: TimestampedSample[];
    recentBackendDurations: TimestampedSample[];
};

/**
 * Fixed-capacity ring buffer for timestamped numeric samples.
 * O(1) push. toArray() reuses its output array when possible to reduce GC pressure.
 */
class TimestampedRingBuffer {
    private readonly timestamps: Float64Array;
    private readonly values: Float64Array;
    private writeIndex: number = 0;
    private count: number = 0;

    /** Cached array from the last toArray() call — reused if count hasn't changed. */
    private _cachedArray: TimestampedSample[] | null = null;
    private _cachedVersion: number = 0;
    private _version: number = 0;

    constructor(capacity: number) {
        this.timestamps = new Float64Array(capacity);
        this.values = new Float64Array(capacity);
    }

    push(timestamp: number, value: number): void {
        this.timestamps[this.writeIndex] = timestamp;
        this.values[this.writeIndex] = value;
        this.writeIndex = (this.writeIndex + 1) % this.timestamps.length;
        if (this.count < this.timestamps.length) {
            this.count++;
        }
        this._version++;
    }

    /** Return contents in chronological order (oldest → newest). */
    toArray(): TimestampedSample[] {
        // Return cached array if no writes since last call
        if (this._cachedArray !== null && this._cachedVersion === this._version) {
            return this._cachedArray;
        }

        const result = new Array<TimestampedSample>(this.count);
        if (this.count < this.timestamps.length) {
            for (let i = 0; i < this.count; i++) {
                result[i] = {timestamp: this.timestamps[i], value: this.values[i]};
            }
        } else {
            for (let i = 0; i < this.count; i++) {
                const idx = (this.writeIndex + i) % this.timestamps.length;
                result[i] = {timestamp: this.timestamps[idx], value: this.values[idx]};
            }
        }

        this._cachedArray = result;
        this._cachedVersion = this._version;
        return result;
    }

    getCount(): number {
        return this.count;
    }

    clear(): void {
        this.writeIndex = 0;
        this.count = 0;
        this._cachedArray = null;
        this._version++;
    }
}

/**
 * Incrementally maintained running statistics for a stream of duration samples.
 * Uses Welford's online algorithm for variance — O(1) per update, no sorting.
 * Median is approximated by tracking a sorted insertion array that is rebuilt
 * only when the ring buffer wraps (i.e. every MAX_DURATION_HISTORY samples).
 */
class RunningStats {
    private _count: number = 0;
    private _sum: number = 0;
    private _m2: number = 0; // sum of squared deviations (Welford)
    private _min: number = Infinity;
    private _max: number = -Infinity;

    /** Ring buffer values for median — rebuilt lazily on snapshot. */
    private _dirty: boolean = false;
    private _sortedCache: Float64Array | null = null;

    /** Reference to the ring buffer to pull raw values for median calculation. */
    private _buffer: TimestampedRingBuffer;

    constructor(buffer: TimestampedRingBuffer) {
        this._buffer = buffer;
    }

    update(value: number): void {
        this._count++;
        this._sum += value;

        // Welford's running variance
        const mean = this._sum / this._count;
        const delta = value - mean;
        this._m2 += delta * (value - mean);

        if (value < this._min) this._min = value;
        if (value > this._max) this._max = value;
        this._dirty = true;
    }

    /** Compute aggregate stats. Sorting only happens here (at snapshot frequency, ~4Hz). */
    computeAggregate(source: string): DetailedFramerate | null {
        if (this._count === 0) return null;

        const mean = this._sum / this._count;
        const variance = this._count > 1 ? this._m2 / this._count : 0;
        const stddev = Math.sqrt(variance);
        const cv = mean > 0 ? stddev / mean : 0;

        // Median: sort only when dirty
        let median = mean; // fallback
        if (this._dirty || this._sortedCache === null) {
            const samples = this._buffer.toArray();
            const durations = new Float64Array(samples.length);
            for (let i = 0; i < samples.length; i++) {
                durations[i] = samples[i].value;
            }
            durations.sort();
            this._sortedCache = durations;
            this._dirty = false;
        }

        const sorted = this._sortedCache;
        const n = sorted.length;
        if (n > 0) {
            median = n % 2 === 0
                ? (sorted[n / 2 - 1] + sorted[n / 2]) / 2
                : sorted[Math.floor(n / 2)];
        }

        return {
            mean_frame_duration_ms: mean,
            mean_frames_per_second: mean > 0 ? 1000 / mean : 0,
            frame_duration_mean: mean,
            frame_duration_median: median,
            frame_duration_min: this._min,
            frame_duration_max: this._max,
            frame_duration_stddev: stddev,
            frame_duration_coefficient_of_variation: cv,
            calculation_window_size: this._count,
            framerate_source: source,
        };
    }

    clear(): void {
        this._count = 0;
        this._sum = 0;
        this._m2 = 0;
        this._min = Infinity;
        this._max = -Infinity;
        this._sortedCache = null;
        this._dirty = false;
    }
}

/**
 * Mutable store for streaming framerate telemetry.
 * Lives in a ref — no Redux, no immutable copies, no re-renders on every update.
 * Components poll via getSnapshot() on their own schedule.
 *
 * Uses incremental statistics (RunningStats) so getSnapshot() is cheap.
 */
export class FramerateStore {
    currentBackendFramerate: DetailedFramerate | null = null;
    currentFrontendFramerate: DetailedFramerate | null = null;

    private _recentFrontendDurations = new TimestampedRingBuffer(MAX_DURATION_HISTORY);
    private _recentBackendDurations = new TimestampedRingBuffer(MAX_DURATION_HISTORY);
    private _frontendStats = new RunningStats(this._recentFrontendDurations);
    private _backendStats = new RunningStats(this._recentBackendDurations);

    updateBackend(data: DetailedFramerate): void {
        this.currentBackendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentBackendDurations.push(Date.now(), data.mean_frame_duration_ms);
            this._backendStats.update(data.mean_frame_duration_ms);
        }
    }

    updateFrontend(data: DetailedFramerate): void {
        this.currentFrontendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentFrontendDurations.push(Date.now(), data.mean_frame_duration_ms);
            this._frontendStats.update(data.mean_frame_duration_ms);
        }
    }

    /** Returns a snapshot for React components to read during render. */
    getSnapshot(): FramerateSnapshot {
        return {
            currentBackendFramerate: this.currentBackendFramerate,
            currentFrontendFramerate: this.currentFrontendFramerate,
            aggregateBackendFramerate: this._backendStats.computeAggregate(
                this.currentBackendFramerate?.framerate_source ?? "Server",
            ),
            aggregateFrontendFramerate: this._frontendStats.computeAggregate(
                this.currentFrontendFramerate?.framerate_source ?? "Display",
            ),
            recentFrontendDurations: this._recentFrontendDurations.toArray(),
            recentBackendDurations: this._recentBackendDurations.toArray(),
        };
    }

    clear(): void {
        this.currentBackendFramerate = null;
        this.currentFrontendFramerate = null;
        this._recentFrontendDurations.clear();
        this._recentBackendDurations.clear();
        this._frontendStats.clear();
        this._backendStats.clear();
    }
}
