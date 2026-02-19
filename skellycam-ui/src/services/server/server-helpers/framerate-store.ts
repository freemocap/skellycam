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

/** Snapshot of all framerate data, returned by getSnapshot(). */
export type FramerateSnapshot = {
    currentBackendFramerate: DetailedFramerate | null;
    currentFrontendFramerate: DetailedFramerate | null;
    recentFrontendFrameDurations: number[];
    recentBackendFrameDurations: number[];
};

/**
 * Fixed-capacity ring buffer for streaming numeric data.
 * O(1) push, O(n) toArray (only called on snapshot requests at ~1Hz).
 * Avoids the repeated Array.slice() copies that occur with push+truncate.
 */
class RingBuffer {
    private readonly buffer: Float64Array;
    private writeIndex: number = 0;
    private count: number = 0;

    constructor(capacity: number) {
        this.buffer = new Float64Array(capacity);
    }

    push(value: number): void {
        this.buffer[this.writeIndex] = value;
        this.writeIndex = (this.writeIndex + 1) % this.buffer.length;
        if (this.count < this.buffer.length) {
            this.count++;
        }
    }

    /** Return contents in chronological order (oldest → newest). */
    toArray(): number[] {
        if (this.count < this.buffer.length) {
            // Buffer hasn't wrapped yet — simple subarray copy
            return Array.from(this.buffer.subarray(0, this.count));
        }
        // Buffer has wrapped — oldest data starts at writeIndex
        const result = new Array<number>(this.count);
        for (let i = 0; i < this.count; i++) {
            result[i] = this.buffer[(this.writeIndex + i) % this.buffer.length];
        }
        return result;
    }

    clear(): void {
        this.writeIndex = 0;
        this.count = 0;
    }
}

/**
 * Mutable store for streaming framerate telemetry.
 * Lives in a ref — no Redux, no immutable copies, no re-renders on every update.
 * Components poll via getSnapshot() on their own schedule.
 */
export class FramerateStore {
    currentBackendFramerate: DetailedFramerate | null = null;
    currentFrontendFramerate: DetailedFramerate | null = null;

    private _recentFrontendFrameDurations = new RingBuffer(MAX_DURATION_HISTORY);
    private _recentBackendFrameDurations = new RingBuffer(MAX_DURATION_HISTORY);

    updateBackend(data: DetailedFramerate): void {
        this.currentBackendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentBackendFrameDurations.push(data.mean_frame_duration_ms);
        }
    }

    updateFrontend(data: DetailedFramerate): void {
        this.currentFrontendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentFrontendFrameDurations.push(data.mean_frame_duration_ms);
        }
    }

    /** Returns a snapshot for React components to read during render. */
    getSnapshot(): FramerateSnapshot {
        return {
            currentBackendFramerate: this.currentBackendFramerate,
            currentFrontendFramerate: this.currentFrontendFramerate,
            recentFrontendFrameDurations: this._recentFrontendFrameDurations.toArray(),
            recentBackendFrameDurations: this._recentBackendFrameDurations.toArray(),
        };
    }

    clear(): void {
        this.currentBackendFramerate = null;
        this.currentFrontendFramerate = null;
        this._recentFrontendFrameDurations.clear();
        this._recentBackendFrameDurations.clear();
    }
}
