// src/services/server/framerate-store.ts

const MAX_DURATION_HISTORY = 10000;

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
 * Mutable store for streaming framerate telemetry.
 * Lives in a ref — no Redux, no immutable copies, no re-renders on every update.
 * Components poll via getSnapshot() on their own schedule.
 */
export class FramerateStore {
    currentBackendFramerate: DetailedFramerate | null = null;
    currentFrontendFramerate: DetailedFramerate | null = null;

    private _recentFrontendFrameDurations: number[] = [];
    private _recentBackendFrameDurations: number[] = [];

    updateBackend(data: DetailedFramerate): void {
        this.currentBackendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentBackendFrameDurations.push(data.mean_frame_duration_ms);
            if (this._recentBackendFrameDurations.length > MAX_DURATION_HISTORY) {
                this._recentBackendFrameDurations = this._recentBackendFrameDurations.slice(-MAX_DURATION_HISTORY);
            }
        }
    }

    updateFrontend(data: DetailedFramerate): void {
        this.currentFrontendFramerate = data;
        if (data.mean_frame_duration_ms > 0) {
            this._recentFrontendFrameDurations.push(data.mean_frame_duration_ms);
            if (this._recentFrontendFrameDurations.length > MAX_DURATION_HISTORY) {
                this._recentFrontendFrameDurations = this._recentFrontendFrameDurations.slice(-MAX_DURATION_HISTORY);
            }
        }
    }

    /** Returns a snapshot for React components to read during render. */
    getSnapshot(): FramerateSnapshot {
        return {
            currentBackendFramerate: this.currentBackendFramerate,
            currentFrontendFramerate: this.currentFrontendFramerate,
            recentFrontendFrameDurations: this._recentFrontendFrameDurations,
            recentBackendFrameDurations: this._recentBackendFrameDurations,
        };
    }

    clear(): void {
        this.currentBackendFramerate = null;
        this.currentFrontendFramerate = null;
        this._recentFrontendFrameDurations = [];
        this._recentBackendFrameDurations = [];
    }
}
