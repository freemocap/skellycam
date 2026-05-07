/**
 * RecordingBrowser — lists available recording sessions from the server,
 * with search filtering, multi-field sorting, and rich per-recording metadata.
 *
 * Standalone component: only depends on CSS utility classes + server URL helper.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import clsx from 'clsx';
import { serverUrls } from '@/services/server/server-helpers/server-urls';
import { backendFetch } from '@/services/electron-ipc/backend-fetch';
import { useTranslation } from 'react-i18next';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape returned by GET /skellycam/playback/recordings */
interface RecordingEntry {
    name: string;
    path: string;
    video_count: number;
    total_size_bytes?: number;
    created_timestamp?: string;
    total_frames?: number;
    duration_seconds?: number;
    fps?: number;
}

/** Shape passed up to the parent when a recording is loaded */
export interface LoadedVideo {
    videoId: string;
    filename: string;
    streamUrl: string;
    sizeBytes: number;
}

interface RecordingBrowserProps {
    onRecordingLoaded: (videos: LoadedVideo[], recordingId: string, recordingPath: string, recordingFps?: number) => void;
    /** If set, automatically load this recording path on mount. */
    initialLoadPath?: string | null;
}

type SortField = 'date' | 'name' | 'size' | 'cameras' | 'frames' | 'duration';
type SortDirection = 'asc' | 'desc';

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
    if (bytes <= 0) return '0 B';
    const k = 1024;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
}

function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    if (m >= 60) {
        const h = Math.floor(m / 60);
        const rm = m % 60;
        return `${h}h ${rm}m ${s}s`;
    }
    return `${m}m ${s}s`;
}

/**
 * Try to parse an ISO-like timestamp from a recording folder name.
 * Handles patterns like:
 *   2026-02-18_09-24-12_GMT-5
 *   2026-02-18T09_24_12
 *   2026-02-18
 */
function parseTimestampFromName(name: string): Date | null {
    // Full datetime: 2026-02-18_09-24-12 or 2026-02-18T09:24:12
    const fullMatch = name.match(
        /(\d{4})-(\d{2})-(\d{2})[T_](\d{2})[_:\-](\d{2})[_:\-](\d{2})/
    );
    if (fullMatch) {
        const [, y, mo, d, h, mi, s] = fullMatch;
        return new Date(+y, +mo - 1, +d, +h, +mi, +s);
    }
    // Date only: 2026-02-18
    const dateMatch = name.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (dateMatch) {
        const [, y, mo, d] = dateMatch;
        return new Date(+y, +mo - 1, +d);
    }
    return null;
}

function formatRelativeTime(date: Date): string {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
}

// ---------------------------------------------------------------------------
// Sort helpers
// ---------------------------------------------------------------------------

function getSortValue(rec: RecordingEntry, field: SortField): number | string {
    switch (field) {
        case 'date': {
            const d = parseTimestampFromName(rec.name);
            return d ? d.getTime() : 0;
        }
        case 'name':
            return rec.name.toLowerCase();
        case 'size':
            return rec.total_size_bytes ?? 0;
        case 'cameras':
            return rec.video_count;
        case 'frames':
            return rec.total_frames ?? 0;
        case 'duration':
            return rec.duration_seconds ?? 0;
    }
}

function compareRecordings(
    a: RecordingEntry,
    b: RecordingEntry,
    field: SortField,
    direction: SortDirection,
): number {
    const va = getSortValue(a, field);
    const vb = getSortValue(b, field);
    let cmp: number;
    if (typeof va === 'string' && typeof vb === 'string') {
        cmp = va.localeCompare(vb);
    } else {
        cmp = (va as number) - (vb as number);
    }
    return direction === 'desc' ? -cmp : cmp;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SORT_OPTIONS: { value: SortField; labelKey: string }[] = [
    { value: 'date', labelKey: 'date' },
    { value: 'name', labelKey: 'name' },
    { value: 'size', labelKey: 'size' },
    { value: 'cameras', labelKey: 'cameras' },
    { value: 'frames', labelKey: 'frames' },
    { value: 'duration', labelKey: 'duration' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const RecordingBrowser: React.FC<RecordingBrowserProps> = ({ onRecordingLoaded, initialLoadPath }) => {
    const { t } = useTranslation();

    // Data state
    const [recordings, setRecordings] = useState<RecordingEntry[]>([]);
    const [isLoadingList, setIsLoadingList] = useState(false);
    const [isLoadingRecording, setIsLoadingRecording] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loadingPath, setLoadingPath] = useState<string | null>(null);

    // Manual path input
    const [manualPath, setManualPath] = useState('');

    // Filter / sort
    const [filterText, setFilterText] = useState('');
    const [sortField, setSortField] = useState<SortField>('date');
    const [sortDir, setSortDir] = useState<SortDirection>('desc');

    // -----------------------------------------------------------------------
    // Fetch the list of recordings from the server
    // -----------------------------------------------------------------------
    const fetchRecordings = useCallback(async () => {
        setIsLoadingList(true);
        setError(null);
        try {
            const response = await backendFetch(serverUrls.endpoints.playbackRecordings);
            if (!response.ok) {
                throw new Error(`Failed to fetch recordings: ${response.statusText}`);
            }
            const data: RecordingEntry[] = await response.json();
            setRecordings(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : t('failedToFetch'));
        } finally {
            setIsLoadingList(false);
        }
    }, []);

    useEffect(() => {
        fetchRecordings();
    }, [fetchRecordings]);

    // -----------------------------------------------------------------------
    // Apply filter + sort
    // -----------------------------------------------------------------------
    const filteredSorted = useMemo(() => {
        let result = recordings;

        // Text filter
        if (filterText.trim()) {
            const q = filterText.trim().toLowerCase();
            result = result.filter((r) => r.name.toLowerCase().includes(q));
        }

        // Sort
        return [...result].sort((a, b) => compareRecordings(a, b, sortField, sortDir));
    }, [recordings, filterText, sortField, sortDir]);

    // -----------------------------------------------------------------------
    // Load a specific recording
    // -----------------------------------------------------------------------
    const loadRecording = useCallback(
        async (recording: RecordingEntry) => {
            setIsLoadingRecording(true);
            setLoadingPath(recording.path);
            setError(null);

            try {
                // If the recording has a full path, derive the parent directory
                // to pass as recording_parent_directory query param for non-standard locations
                let videosUrl = serverUrls.endpoints.playbackVideos(recording.name);
                if (recording.path) {
                    const normalized = recording.path.replace(/\\/g, '/').replace(/\/+$/, '');
                    const lastSlash = normalized.lastIndexOf('/');
                    if (lastSlash >= 0) {
                        const parentDir = normalized.slice(0, lastSlash);
                        videosUrl += `?recording_parent_directory=${encodeURIComponent(parentDir)}`;
                    }
                }

                const response = await backendFetch(videosUrl);

                if (!response.ok) {
                    const detail = await response
                        .json()
                        .catch(() => ({ detail: response.statusText }));
                    throw new Error(detail.detail || response.statusText);
                }

                const data: Array<{
                    video_id: string;
                    filename: string;
                    stream_url: string;
                    size_bytes: number;
                }> = await response.json();

                const videos: LoadedVideo[] = data.map((v) => ({
                    videoId: v.video_id,
                    filename: v.filename,
                    streamUrl: serverUrls.endpoints.playbackVideoStream(recording.name, v.video_id),
                    sizeBytes: v.size_bytes,
                }));

                const recFps = recording.fps ?? undefined;

                onRecordingLoaded(videos, recording.name, recording.path, recFps);
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Failed to load recording');
            } finally {
                setIsLoadingRecording(false);
                setLoadingPath(null);
            }
        },
        [onRecordingLoaded],
    );

    // Auto-load a recording if initialLoadPath is provided
    const [didAutoLoad, setDidAutoLoad] = useState(false);
    useEffect(() => {
        if (initialLoadPath && !didAutoLoad) {
            setDidAutoLoad(true);
            // Derive recording_id (folder name) and parent from the full path
            const normalized = initialLoadPath.replace(/[\\/]+$/, '');
            const lastSep = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'));
            const recName = lastSep >= 0 ? normalized.slice(lastSep + 1) : normalized;
            const recPath = initialLoadPath;
            loadRecording({ name: recName, path: recPath, video_count: 0 });
        }
    }, [initialLoadPath, didAutoLoad, loadRecording]);

    const handleLoadManualPath = useCallback(() => {
        const trimmed = manualPath.trim().replace(/[\\/]+$/, '');
        if (!trimmed) return;
        const lastSep = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
        const recName = lastSep >= 0 ? trimmed.slice(lastSep + 1) : trimmed;
        loadRecording({ name: recName, path: trimmed, video_count: 0 });
    }, [manualPath, loadRecording]);

    // -----------------------------------------------------------------------
    // Sort controls
    // -----------------------------------------------------------------------
    const handleSortFieldChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        setSortField(e.target.value as SortField);
    };

    const toggleSortDir = () => {
        setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    };

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------
    return (
        <div className="flex flex-col gap-2 p-2 h-full overflow-hidden">
            {/* Manual path row */}
            <div className="flex gap-1 items-center">
                <div className="input-with-string flex-1">
                    <input
                        className="input-field"
                        placeholder="~/skellycam_data/recordings/2024-01-01..."
                        value={manualPath}
                        onChange={(e) => setManualPath(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleLoadManualPath();
                        }}
                        disabled={isLoadingRecording}
                    />
                </div>
                <button
                    className="button sm"
                    onClick={handleLoadManualPath}
                    disabled={!manualPath.trim() || isLoadingRecording}
                >
                    {isLoadingRecording && !loadingPath
                        ? <span className="icon loader-icon icon-size-16" />
                        : <span className="icon stream-icon icon-size-16" />}
                    {t('load')}
                </button>
            </div>

            {/* Error */}
            {error && <p className="text sm text-error">{error}</p>}

            {/* Header bar */}
            <div className="flex items-center justify-content-space-between gap-1 flex-wrap">
                <div className="flex items-center gap-1">
                    <p className="text bg text-white">{t('recordings')}</p>
                    {recordings.length > 0 && (
                        <span className="camera-status-badge">
                            {filterText ? `${filteredSorted.length} / ${recordings.length}` : recordings.length}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1">
                    <div className="input-with-string">
                        <input
                            className="input-field"
                            placeholder={t('filter')}
                            value={filterText}
                            onChange={(e) => setFilterText(e.target.value)}
                        />
                    </div>
                    <select
                        className="sort-select input-field"
                        value={sortField}
                        onChange={handleSortFieldChange}
                    >
                        {SORT_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {t(opt.labelKey)}
                            </option>
                        ))}
                    </select>
                    <button
                        className="button icon-button"
                        onClick={toggleSortDir}
                        title="Toggle sort direction"
                    >
                        {sortDir === 'desc' ? '↓' : '↑'}
                    </button>
                    <button
                        className="button sm"
                        onClick={fetchRecordings}
                        disabled={isLoadingList}
                    >
                        <span className="icon rotate-icon icon-size-16" />{t('refresh')}
                    </button>
                </div>
            </div>

            {/* List */}
            {isLoadingList ? (
                <div className="flex items-center justify-center py-4">
                    <span className="icon loader-icon icon-size-16" />
                </div>
            ) : filteredSorted.length === 0 ? (
                <p className="text sm text-gray text-center p-4">
                    {recordings.length === 0
                        ? t('noRecordingsFound')
                        : 'No recordings match your filter.'}
                </p>
            ) : (
                <div className="recording-list flex-1 overflow-y border-1 border-black br-1">
                    {filteredSorted.map((rec) => (
                        <RecordingRow
                            key={rec.path}
                            rec={rec}
                            isLoading={loadingPath === rec.path}
                            isAnyLoading={isLoadingRecording}
                            onClick={() => loadRecording(rec)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// RecordingRow — a single recording in the list
// ---------------------------------------------------------------------------

interface RecordingRowProps {
    rec: RecordingEntry;
    isLoading: boolean;
    isAnyLoading: boolean;
    onClick: () => void;
}

const RecordingRow: React.FC<RecordingRowProps> = React.memo(
    ({ rec, isLoading, isAnyLoading, onClick }) => {
        const parsedDate = parseTimestampFromName(rec.name);
        const { t } = useTranslation();

        return (
            <div
                className={clsx("recording-row toggle-button flex flex-col gap-1 p-2", isAnyLoading && !isLoading && "recording-row-disabled")}
                onClick={!isAnyLoading ? onClick : undefined}
            >
                <div className="flex items-center gap-1">
                    {isLoading
                        ? <span className="icon loader-icon icon-size-16" />
                        : <span className="icon import-icon icon-size-16" />}
                    <p className="text sm recording-name">{rec.name}</p>
                </div>
                <div className="flex flex-wrap gap-2 items-center">
                    <span className="text sm text-gray" title="Camera streams">
                        {rec.video_count} cam{rec.video_count !== 1 ? 's' : ''}
                    </span>
                    {rec.total_size_bytes != null && rec.total_size_bytes > 0 && (
                        <span className="text sm text-gray" title="Total size">
                            {formatBytes(rec.total_size_bytes)}
                        </span>
                    )}
                    {rec.duration_seconds != null && rec.duration_seconds > 0 && (
                        <span className="text sm text-gray" title="Duration">
                            {formatDuration(rec.duration_seconds)}
                        </span>
                    )}
                    {rec.total_frames != null && rec.total_frames > 0 && (
                        <span className="camera-config-chip" title={t('frameCountPerCamera')}>
                            {rec.total_frames.toLocaleString()} frames
                        </span>
                    )}
                    {rec.fps != null && rec.fps > 0 && (
                        <span className="camera-config-chip" title={t('recordingCaptureFps')}>
                            {rec.fps} fps
                        </span>
                    )}
                    {parsedDate && (
                        <span
                            className="text sm text-gray"
                            style={{ fontStyle: 'italic' }}
                            title={parsedDate.toLocaleString()}
                        >
                            {formatRelativeTime(parsedDate)}
                        </span>
                    )}
                </div>
            </div>
        );
    },
);

RecordingRow.displayName = 'RecordingRow';
