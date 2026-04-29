/**
 * fetchWithTimeout — wraps fetch() with an AbortSignal timeout.
 *
 * When the signal fires, the DOMException is caught and re-thrown as a plain
 * Error with a user-readable message, so callers don't need to inspect
 * DOMException.name themselves.
 */

// Timeout durations in milliseconds, tuned to each operation's expected cost.
export const FETCH_TIMEOUTS = {
    /** USB camera enumeration — fast but may scan multiple buses. */
    CAMERA_DETECT: 10_000,
    /** Opening cameras, setting resolution/fps, allocating ring buffers.
     *  With 4+ cameras this can approach 30s on slow USB controllers. */
    CAMERA_CONNECT: 45_000,
    /** Sending stop-workers signal — should resolve within 1-2s. */
    CAMERA_CLOSE: 10_000,
    /** Flips a single shared flag — nearly instant. */
    CAMERA_PAUSE: 5_000,
    /** Starts video writers and kicks off the recording loop — fast. */
    RECORD_START: 8_000,
    /** Flushes camera buffers, closes writers, remuxes audio/video.
     *  May take several seconds for long or multi-camera recordings. */
    RECORD_STOP: 25_000,
    /** Audio device enumeration — fast. */
    MIC_DETECT: 8_000,
    /** Directory listing of all recordings. */
    PLAYBACK_LIST: 10_000,
    /** Directory listing + per-file stat calls for a single recording. */
    PLAYBACK_LOAD: 10_000,
    /** Reading timestamp CSV files for a recording. */
    PLAYBACK_TIMESTAMPS: 10_000,
} as const;

export async function fetchWithTimeout(
    url: string,
    init?: RequestInit,
    timeoutMs: number = 10_000,
): Promise<Response> {
    try {
        return await fetch(url, {
            ...init,
            signal: AbortSignal.timeout(timeoutMs),
        });
    } catch (e) {
        if (e instanceof DOMException && (e.name === 'TimeoutError' || e.name === 'AbortError')) {
            throw new Error(
                `Request timed out after ${timeoutMs / 1000}s — the server may be busy. Please try again.`,
            );
        }
        throw e;
    }
}
