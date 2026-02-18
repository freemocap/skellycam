import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Tooltip, Typography, useTheme } from '@mui/material';
import { PlaybackControls } from './PlaybackControls';

interface VideoEntry {
    videoId: string;
    filename: string;
    streamUrl: string;
}

export interface PlaybackSettings {
    showOverlays: boolean;
    timestampFormat: 'timecode' | 'seconds';
}

interface SyncedVideoPlayerProps {
    videos: VideoEntry[];
    recordingFps?: number;
}

function formatTimecode(frame: number, fps: number): string {
    if (fps <= 0) return '00:00:00:00';
    const totalSec = frame / fps;
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = Math.floor(totalSec % 60);
    const f = frame % Math.round(fps);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

function formatSeconds(frame: number, fps: number): string {
    if (fps <= 0) return '0.000s';
    return `${(frame / fps).toFixed(3)}s`;
}

/**
 * High-performance frame-locked multi-video player.
 *
 * CRITICAL PERFORMANCE DESIGN:
 * During playback, we NEVER call React setState per-frame. Instead:
 *   - Frame number overlays are updated via direct DOM manipulation (refs)
 *   - React state (for controls/slider) is updated at ~5Hz via a throttle
 *   - Videos use native .play() with periodic drift correction
 *
 * This keeps the rAF loop ~0ms per tick with zero React re-renders during playback.
 */
export const SyncedVideoPlayer: React.FC<SyncedVideoPlayerProps> = ({ videos, recordingFps }) => {
    const theme = useTheme();
    const videoRefs = useRef<Map<string, HTMLVideoElement>>(new Map());

    // Direct DOM refs for overlays — updated WITHOUT React re-renders
    const frameOverlayRefs = useRef<Map<string, HTMLElement>>(new Map());
    const timeOverlayRefs = useRef<Map<string, HTMLElement>>(new Map());

    // Playback refs (rAF loop reads these, never stale)
    const isPlayingRef = useRef(false);
    const currentFrameRef = useRef(0);
    const totalFramesRef = useRef(0);
    const fpsRef = useRef(recordingFps || 30);
    const playbackRateRef = useRef(1);
    const playStartTimeRef = useRef<number | null>(null);
    const playStartFrameRef = useRef(0);
    const rafRef = useRef<number | null>(null);
    const syncCheckCounter = useRef(0);
    const settingsRef = useRef<PlaybackSettings>({ showOverlays: true, timestampFormat: 'seconds' });

    const SYNC_CHECK_INTERVAL = 3;
    const SYNC_TOLERANCE_FRAMES = 0.5;
    // Grace period: skip sync corrections for the first N ms after play starts
    // to let the browser's video decoder buffer and stabilize
    const SYNC_GRACE_PERIOD_MS = 600;

    // Throttle: only push to React state every ~200ms
    const lastReactUpdateRef = useRef(0);
    const REACT_UPDATE_INTERVAL_MS = 200;

    // Slider drag state — tracked in refs so rAF loop can read it
    const isDraggingRef = useRef(false);
    const wasPlayingBeforeDragRef = useRef(false);

    // React state — ONLY for controls/slider, NOT updated per-frame
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentFrame, setCurrentFrame] = useState(0);
    const [totalFrames, setTotalFrames] = useState(0);
    const [duration, setDuration] = useState(0);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [videosReady, setVideosReady] = useState(0);
    const [settings, setSettings] = useState<PlaybackSettings>({
        showOverlays: true,
        timestampFormat: 'seconds',
    });

    const fps = recordingFps || 30;
    const allReady = videosReady >= videos.length && videos.length > 0;
    const columns = videos.length <= 1 ? 1 : videos.length <= 4 ? 2 : videos.length <= 9 ? 3 : 4;
    const currentTime = fpsRef.current > 0 ? currentFrameRef.current / fpsRef.current : 0;

    // Keep settingsRef in sync
    useEffect(() => { settingsRef.current = settings; }, [settings]);

    useEffect(() => {
        if (recordingFps && recordingFps > 0) fpsRef.current = recordingFps;
    }, [recordingFps]);

    // -----------------------------------------------------------------------
    // Direct DOM overlay updates — fast, no React involved
    // -----------------------------------------------------------------------
    const updateOverlays = useCallback((frame: number) => {
        const s = settingsRef.current;
        const padLen = Math.max(String(totalFramesRef.current).length, 1);
        const frameText = 'F' + String(frame).padStart(padLen, '0');
        const timeText = '~' + (s.timestampFormat === 'timecode'
            ? formatTimecode(frame, fpsRef.current)
            : formatSeconds(frame, fpsRef.current));

        frameOverlayRefs.current.forEach((el) => { el.textContent = frameText; });
        timeOverlayRefs.current.forEach((el) => { el.textContent = timeText; });
    }, []);

    // -----------------------------------------------------------------------
    // Ref registration
    // -----------------------------------------------------------------------
    const setVideoRef = useCallback((videoId: string, el: HTMLVideoElement | null) => {
        if (el) videoRefs.current.set(videoId, el);
        else videoRefs.current.delete(videoId);
    }, []);

    const setFrameOverlayRef = useCallback((videoId: string, el: HTMLElement | null) => {
        if (el) frameOverlayRefs.current.set(videoId, el);
        else frameOverlayRefs.current.delete(videoId);
    }, []);

    const setTimeOverlayRef = useCallback((videoId: string, el: HTMLElement | null) => {
        if (el) timeOverlayRefs.current.set(videoId, el);
        else timeOverlayRefs.current.delete(videoId);
    }, []);

    // -----------------------------------------------------------------------
    // Seek all videos to a frame (used when PAUSED / stepping only)
    // -----------------------------------------------------------------------
    const seekAllToFrame = useCallback((frame: number) => {
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        const targetTime = fpsRef.current > 0 ? clamped / fpsRef.current : 0;
        videoRefs.current.forEach((el) => { el.currentTime = targetTime; });
        currentFrameRef.current = clamped;
        setCurrentFrame(clamped);      // OK when paused — not per-frame
        updateOverlays(clamped);
    }, [updateOverlays]);

    // -----------------------------------------------------------------------
    // Native play/pause
    // -----------------------------------------------------------------------
    const playAllVideos = useCallback(() => {
        videoRefs.current.forEach((el) => {
            el.playbackRate = playbackRateRef.current;
            el.play().catch(() => {});
        });
    }, []);

    const pauseAllVideos = useCallback(() => {
        videoRefs.current.forEach((el) => { el.pause(); });
    }, []);

    // -----------------------------------------------------------------------
    // rAF playback loop — ZERO React state updates per frame
    // -----------------------------------------------------------------------
    const tick = useCallback((timestamp: DOMHighResTimeStamp) => {
        if (!isPlayingRef.current) return;

        if (playStartTimeRef.current === null) {
            playStartTimeRef.current = timestamp;
            lastReactUpdateRef.current = timestamp;
        }

        const elapsedSec = (timestamp - playStartTimeRef.current) / 1000;
        const newFrame = playStartFrameRef.current + (elapsedSec * fpsRef.current * playbackRateRef.current);

        // End of video
        if (newFrame >= totalFramesRef.current) {
            pauseAllVideos();
            isPlayingRef.current = false;
            playStartTimeRef.current = null;
            const endFrame = totalFramesRef.current - 1;
            currentFrameRef.current = endFrame;
            updateOverlays(endFrame);
            // Single React update on stop
            setIsPlaying(false);
            setCurrentFrame(endFrame);
            return;
        }

        const intFrame = Math.floor(newFrame);
        const prevIntFrame = Math.floor(currentFrameRef.current);
        currentFrameRef.current = newFrame;

        // Update DOM overlays directly on frame change — FAST
        if (intFrame !== prevIntFrame) {
            updateOverlays(intFrame);
        }

        // Throttled React update for controls/slider (~5Hz)
        if (timestamp - lastReactUpdateRef.current >= REACT_UPDATE_INTERVAL_MS) {
            lastReactUpdateRef.current = timestamp;
            setCurrentFrame(intFrame);
        }

        // Periodic video sync check — skip during grace period after start
        syncCheckCounter.current++;
        const elapsedMs = timestamp - playStartTimeRef.current!;
        if (syncCheckCounter.current >= SYNC_CHECK_INTERVAL && elapsedMs > SYNC_GRACE_PERIOD_MS) {
            syncCheckCounter.current = 0;
            const targetTime = newFrame / fpsRef.current;
            const toleranceSec = SYNC_TOLERANCE_FRAMES / fpsRef.current;
            videoRefs.current.forEach((el) => {
                if (Math.abs(el.currentTime - targetTime) > toleranceSec) el.currentTime = targetTime;
                if (Math.abs(el.playbackRate - playbackRateRef.current) > 0.01) el.playbackRate = playbackRateRef.current;
            });
        }

        rafRef.current = requestAnimationFrame(tick);
    }, [pauseAllVideos, updateOverlays]);

    const startLoop = useCallback(() => {
        playStartTimeRef.current = null;
        playStartFrameRef.current = Math.floor(currentFrameRef.current);
        syncCheckCounter.current = 0;
        rafRef.current = requestAnimationFrame(tick);
    }, [tick]);

    const stopLoop = useCallback(() => {
        if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
        playStartTimeRef.current = null;
    }, []);

    useEffect(() => stopLoop, [stopLoop]);

    // -----------------------------------------------------------------------
    // Metadata
    // -----------------------------------------------------------------------
    const handleLoadedMetadata = useCallback((e: React.SyntheticEvent<HTMLVideoElement>) => {
        const el = e.currentTarget;
        if (el.duration && el.duration !== Infinity) {
            const d = el.duration;
            setDuration((prev) => Math.max(prev, d));
            const frames = Math.floor(d * fpsRef.current);
            if (totalFramesRef.current === 0 || frames < totalFramesRef.current) {
                totalFramesRef.current = frames;
                setTotalFrames(frames);
            }
        }
        el.pause();
        setVideosReady((prev) => prev + 1);
    }, []);

    // -----------------------------------------------------------------------
    // Playback commands
    // -----------------------------------------------------------------------
    const handlePlayPause = useCallback(() => {
        if (isPlayingRef.current) {
            isPlayingRef.current = false; stopLoop(); pauseAllVideos(); setIsPlaying(false);
            seekAllToFrame(Math.floor(currentFrameRef.current));
        } else {
            if (Math.floor(currentFrameRef.current) >= totalFramesRef.current - 1) seekAllToFrame(0);
            isPlayingRef.current = true; setIsPlaying(true); playAllVideos(); startLoop();
        }
    }, [seekAllToFrame, startLoop, stopLoop, playAllVideos, pauseAllVideos]);

    // Slider DRAG — lightweight: just update overlays + pause once, no play/restart
    const handleSeekDrag = useCallback((frame: number) => {
        if (!isDraggingRef.current) {
            // First drag tick — pause if playing
            isDraggingRef.current = true;
            wasPlayingBeforeDragRef.current = isPlayingRef.current;
            if (isPlayingRef.current) {
                isPlayingRef.current = false;
                stopLoop();
                pauseAllVideos();
            }
        }
        // Update overlays instantly via DOM
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        currentFrameRef.current = clamped;
        updateOverlays(clamped);
        setCurrentFrame(clamped);
        // Seek videos (they're paused, so this is just setting the poster frame)
        const targetTime = fpsRef.current > 0 ? clamped / fpsRef.current : 0;
        videoRefs.current.forEach((el) => { el.currentTime = targetTime; });
    }, [stopLoop, pauseAllVideos, updateOverlays]);

    // Slider COMMIT — final seek + resume if was playing
    const handleSeekCommit = useCallback((frame: number) => {
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        seekAllToFrame(clamped);
        if (wasPlayingBeforeDragRef.current) {
            isPlayingRef.current = true;
            setIsPlaying(true);
            playAllVideos();
            startLoop();
        }
        isDraggingRef.current = false;
        wasPlayingBeforeDragRef.current = false;
    }, [seekAllToFrame, playAllVideos, startLoop]);

    const handleFrameStep = useCallback((delta: number) => {
        if (isPlayingRef.current) { isPlayingRef.current = false; stopLoop(); pauseAllVideos(); setIsPlaying(false); }
        seekAllToFrame(Math.floor(currentFrameRef.current) + delta);
    }, [seekAllToFrame, stopLoop, pauseAllVideos]);

    const handlePlaybackRateChange = useCallback((rate: number) => {
        playbackRateRef.current = rate; setPlaybackRate(rate);
        if (isPlayingRef.current) {
            videoRefs.current.forEach((el) => { el.playbackRate = rate; });
            playStartTimeRef.current = null;
            playStartFrameRef.current = Math.floor(currentFrameRef.current);
        }
    }, []);

    const handleSeekToStart = useCallback(() => {
        const w = isPlayingRef.current;
        if (w) { isPlayingRef.current = false; stopLoop(); pauseAllVideos(); }
        seekAllToFrame(0);
        if (w) { isPlayingRef.current = true; setIsPlaying(true); playAllVideos(); startLoop(); }
    }, [seekAllToFrame, stopLoop, startLoop, playAllVideos, pauseAllVideos]);

    const handleSeekToEnd = useCallback(() => {
        if (isPlayingRef.current) { isPlayingRef.current = false; stopLoop(); pauseAllVideos(); setIsPlaying(false); }
        seekAllToFrame(totalFramesRef.current - 1);
    }, [seekAllToFrame, stopLoop, pauseAllVideos]);

    // -----------------------------------------------------------------------
    // Keyboard
    // -----------------------------------------------------------------------
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
            switch (e.key) {
                case ' ': e.preventDefault(); handlePlayPause(); break;
                case 'ArrowLeft': e.preventDefault(); handleFrameStep(e.shiftKey ? -10 : -1); break;
                case 'ArrowRight': e.preventDefault(); handleFrameStep(e.shiftKey ? 10 : 1); break;
                case 'Home': e.preventDefault(); handleSeekToStart(); break;
                case 'End': e.preventDefault(); handleSeekToEnd(); break;
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [handlePlayPause, handleFrameStep, handleSeekToStart, handleSeekToEnd]);

    // -----------------------------------------------------------------------
    // Render — overlays use callback refs for direct DOM updates
    // -----------------------------------------------------------------------
    if (videos.length === 0) {
        return (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary' }}>
                <Typography>No videos loaded</Typography>
            </Box>
        );
    }

    const framePadLen = Math.max(String(totalFrames).length, 1);
    const initialFrameText = 'F' + String(currentFrame).padStart(framePadLen, '0');
    const initialTimeText = '~' + (settings.timestampFormat === 'timecode'
        ? formatTimecode(currentFrame, fps)
        : formatSeconds(currentFrame, fps));

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
            {/* Video grid */}
            <Box
                sx={{
                    flex: 1,
                    display: 'grid',
                    gridTemplateColumns: `repeat(${columns}, 1fr)`,
                    gap: '2px',
                    p: '2px',
                    overflow: 'hidden',
                    backgroundColor: '#0a0a0a',
                    minHeight: 0,
                }}
            >
                {videos.map((video) => (
                    <Box
                        key={video.videoId}
                        sx={{
                            position: 'relative',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            backgroundColor: '#000',
                            overflow: 'hidden',
                            minHeight: 120,
                        }}
                    >
                        <video
                            ref={(el) => setVideoRef(video.videoId, el)}
                            src={video.streamUrl}
                            preload="auto"
                            muted
                            playsInline
                            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                            onLoadedMetadata={handleLoadedMetadata}
                        />

                        {settings.showOverlays && (
                            <>
                                {/* FRAME NUMBER — DOM ref, updated directly */}
                                <Box
                                    ref={(el: HTMLElement | null) => setFrameOverlayRef(video.videoId, el)}
                                    sx={{
                                        position: 'absolute', top: 6, right: 6,
                                        backgroundColor: 'rgba(0, 0, 0, 0.88)',
                                        color: '#00ff88',
                                        px: 1.25, py: 0.4, borderRadius: '4px',
                                        fontSize: '14px', fontWeight: 700,
                                        fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", monospace',
                                        letterSpacing: '0.5px', lineHeight: 1,
                                        border: '1px solid rgba(0, 255, 136, 0.3)',
                                        textShadow: '0 0 6px rgba(0, 255, 136, 0.4)',
                                        minWidth: 60, textAlign: 'center',
                                        userSelect: 'none', pointerEvents: 'none', zIndex: 10,
                                    }}
                                >
                                    {initialFrameText}
                                </Box>

                                {/* CAMERA ID — static, never changes */}
                                <Box sx={{
                                    position: 'absolute', bottom: 6, left: 6,
                                    backgroundColor: 'rgba(0, 0, 0, 0.75)',
                                    color: '#ccc', px: 1, py: 0.25, borderRadius: '3px',
                                    fontSize: '11px',
                                    fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                    userSelect: 'none', pointerEvents: 'none', zIndex: 10,
                                }}>
                                    {video.videoId}
                                </Box>

                                {/* TIMECODE — DOM ref, updated directly */}
                                <Tooltip title="Estimated from frame number × recording fps — not read from timestamp data" placement="top-end">
                                    <Box
                                        ref={(el: HTMLElement | null) => setTimeOverlayRef(video.videoId, el)}
                                        sx={{
                                            position: 'absolute', bottom: 6, right: 6,
                                            backgroundColor: 'rgba(0, 0, 0, 0.75)',
                                            color: '#aaa', px: 0.75, py: 0.25, borderRadius: '3px',
                                            fontSize: '10px',
                                            fontFamily: '"JetBrains Mono", "Fira Code", monospace',
                                            userSelect: 'none', zIndex: 10,
                                        }}
                                    >
                                        {initialTimeText}
                                    </Box>
                                </Tooltip>
                            </>
                        )}
                    </Box>
                ))}
            </Box>

            {!allReady && videos.length > 0 && (
                <Box sx={{ textAlign: 'center', py: 0.5, backgroundColor: theme.palette.warning.dark, color: '#fff' }}>
                    <Typography variant="caption">Loading videos… ({videosReady}/{videos.length} ready)</Typography>
                </Box>
            )}

            <PlaybackControls
                isPlaying={isPlaying}
                currentTime={currentTime}
                duration={duration}
                playbackRate={playbackRate}
                currentFrame={currentFrame}
                totalFrames={totalFrames}
                fps={fps}
                recordingFps={recordingFps}
                settings={settings}
                onSettingsChange={setSettings}
                onPlayPause={handlePlayPause}
                onSeekDrag={handleSeekDrag}
                onSeekCommit={handleSeekCommit}
                onFrameStep={handleFrameStep}
                onPlaybackRateChange={handlePlaybackRateChange}
                onSeekToStart={handleSeekToStart}
                onSeekToEnd={handleSeekToEnd}
            />
        </Box>
    );
};
