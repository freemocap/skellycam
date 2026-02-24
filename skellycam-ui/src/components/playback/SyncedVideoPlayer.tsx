import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Tooltip, Typography, useTheme } from '@mui/material';
import { PlaybackControls } from './PlaybackControls';
import { useTranslation } from 'react-i18next';

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
    /** Per-camera frame timestamps in seconds from recording start, loaded from CSV files */
    frameTimestamps?: Record<string, number[]> | null;
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

function formatTimecodeFromSeconds(seconds: number, fps: number): string {
    if (fps <= 0) return '00:00:00:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const f = Math.floor((seconds % 1) * fps);
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

function formatSeconds(frame: number, fps: number): string {
    if (fps <= 0) return '0.000s';
    return `${(frame / fps).toFixed(3)}s`;
}

/**
 * Frame-locked multi-video player using a "leader" video element as the
 * canonical time source. All other videos sync to the leader.
 *
 * SYNC STRATEGY:
 * - The first video is the "leader" and drives canonical time via its
 *   native currentTime property, which naturally accounts for decode
 *   latency, buffering, and rate changes.
 * - The rAF loop reads leader.currentTime to derive the frame number.
 * - Follower videos are corrected ONLY when they drift beyond a generous
 *   tolerance (2 frames), avoiding micro-stutter from frequent seeks.
 * - Overlays update via direct DOM manipulation (zero React re-renders).
 * - React state for controls/slider updates at ~5Hz.
 */
export const SyncedVideoPlayer: React.FC<SyncedVideoPlayerProps> = ({ videos, recordingFps, frameTimestamps }) => {
    const theme = useTheme();
    const { t } = useTranslation();
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
    const rafRef = useRef<number | null>(null);
    const settingsRef = useRef<PlaybackSettings>({ showOverlays: true, timestampFormat: 'seconds' });
    const frameTimestampsRef = useRef<Record<string, number[]> | null>(null);

    // Leader-based sync: first video is the time authority
    const leaderIdRef = useRef<string | null>(null);

    // Follower drift correction: generous tolerance to avoid stutter.
    // Only correct followers that are more than 2 frames away from leader.
    const FOLLOWER_DRIFT_TOLERANCE_FRAMES = 2;
    // Check followers every N rAF ticks (~250ms at 60fps)
    const FOLLOWER_CHECK_INTERVAL = 15;
    const followerCheckCounter = useRef(0);

    // Throttle React state updates to ~5Hz
    const lastReactUpdateRef = useRef(0);
    const REACT_UPDATE_INTERVAL_MS = 200;

    // Slider drag state
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

    // Keep refs in sync with props/state
    useEffect(() => { settingsRef.current = settings; }, [settings]);
    useEffect(() => { frameTimestampsRef.current = frameTimestamps ?? null; }, [frameTimestamps]);
    useEffect(() => {
        if (recordingFps && recordingFps > 0) fpsRef.current = recordingFps;
    }, [recordingFps]);

    // Elect leader whenever video list changes
    useEffect(() => {
        leaderIdRef.current = videos.length > 0 ? videos[0].videoId : null;
    }, [videos]);

    // -----------------------------------------------------------------------
    // Direct DOM overlay updates — fast, no React involved
    // -----------------------------------------------------------------------
    const updateOverlays = useCallback((frame: number) => {
        const s = settingsRef.current;
        const ts = frameTimestampsRef.current;
        const padLen = Math.max(String(totalFramesRef.current).length, 1);
        const frameText = 'F' + String(frame).padStart(padLen, '0');

        let timeText: string;
        if (ts) {
            const firstKey = Object.keys(ts)[0];
            const camTs = firstKey ? ts[firstKey] : null;
            if (camTs && frame < camTs.length) {
                const realSec = camTs[frame];
                timeText = s.timestampFormat === 'timecode'
                    ? formatTimecodeFromSeconds(realSec, fpsRef.current)
                    : `${realSec.toFixed(3)}s`;
            } else {
                timeText = '~' + (s.timestampFormat === 'timecode'
                    ? formatTimecode(frame, fpsRef.current)
                    : formatSeconds(frame, fpsRef.current));
            }
        } else {
            timeText = '~' + (s.timestampFormat === 'timecode'
                ? formatTimecode(frame, fpsRef.current)
                : formatSeconds(frame, fpsRef.current));
        }

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
        setCurrentFrame(clamped);
        updateOverlays(clamped);
    }, [updateOverlays]);

    // -----------------------------------------------------------------------
    // Native play/pause
    // -----------------------------------------------------------------------
    const playAllVideos = useCallback(() => {
        const rate = playbackRateRef.current;
        // Play leader first so it starts decoding immediately
        const leaderId = leaderIdRef.current;
        const leader = leaderId ? videoRefs.current.get(leaderId) : null;
        if (leader) {
            leader.playbackRate = rate;
            leader.play().catch(() => {});
        }
        videoRefs.current.forEach((el, id) => {
            if (id === leaderId) return;
            el.playbackRate = rate;
            el.play().catch(() => {});
        });
    }, []);

    const pauseAllVideos = useCallback(() => {
        videoRefs.current.forEach((el) => { el.pause(); });
    }, []);

    // -----------------------------------------------------------------------
    // rAF playback loop — reads leader.currentTime as the time source.
    //
    // This eliminates the wall-clock-vs-decode-pipeline fight that causes
    // stutter. The leader's currentTime naturally accounts for buffering,
    // decode latency, and rate changes. We just read it and derive frames.
    // -----------------------------------------------------------------------
    const tick = useCallback((timestamp: DOMHighResTimeStamp) => {
        if (!isPlayingRef.current) return;

        const leaderId = leaderIdRef.current;
        const leader = leaderId ? videoRefs.current.get(leaderId) : null;
        if (!leader) {
            rafRef.current = requestAnimationFrame(tick);
            return;
        }

        const leaderTime = leader.currentTime;
        const newFrame = leaderTime * fpsRef.current;

        // End of video
        if (newFrame >= totalFramesRef.current) {
            pauseAllVideos();
            isPlayingRef.current = false;
            const endFrame = totalFramesRef.current - 1;
            currentFrameRef.current = endFrame;
            updateOverlays(endFrame);
            setIsPlaying(false);
            setCurrentFrame(endFrame);
            return;
        }

        const intFrame = Math.floor(newFrame);
        const prevIntFrame = Math.floor(currentFrameRef.current);
        currentFrameRef.current = newFrame;

        // Update DOM overlays on frame change
        if (intFrame !== prevIntFrame) {
            updateOverlays(intFrame);
        }

        // Throttled React update for slider (~5Hz)
        if (timestamp - lastReactUpdateRef.current >= REACT_UPDATE_INTERVAL_MS) {
            lastReactUpdateRef.current = timestamp;
            setCurrentFrame(intFrame);
        }

        // Periodic follower drift correction — only when drift exceeds tolerance.
        // This is the key to smooth playback: let browser-native playback run
        // undisturbed and only intervene when followers genuinely desync.
        followerCheckCounter.current++;
        if (followerCheckCounter.current >= FOLLOWER_CHECK_INTERVAL) {
            followerCheckCounter.current = 0;
            const toleranceSec = FOLLOWER_DRIFT_TOLERANCE_FRAMES / fpsRef.current;
            const rate = playbackRateRef.current;
            videoRefs.current.forEach((el, id) => {
                if (id === leaderId) return;
                if (Math.abs(el.currentTime - leaderTime) > toleranceSec) {
                    el.currentTime = leaderTime;
                }
                if (Math.abs(el.playbackRate - rate) > 0.01) {
                    el.playbackRate = rate;
                }
            });
        }

        rafRef.current = requestAnimationFrame(tick);
    }, [pauseAllVideos, updateOverlays]);

    const startLoop = useCallback(() => {
        followerCheckCounter.current = 0;
        lastReactUpdateRef.current = 0;
        rafRef.current = requestAnimationFrame(tick);
    }, [tick]);

    const stopLoop = useCallback(() => {
        if (rafRef.current !== null) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
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
            isPlayingRef.current = false;
            stopLoop();
            pauseAllVideos();
            setIsPlaying(false);
            // Snap all videos to leader's position on pause for perfect alignment
            const leaderId = leaderIdRef.current;
            const leader = leaderId ? videoRefs.current.get(leaderId) : null;
            if (leader) {
                const pauseFrame = Math.floor(leader.currentTime * fpsRef.current);
                seekAllToFrame(pauseFrame);
            }
        } else {
            if (Math.floor(currentFrameRef.current) >= totalFramesRef.current - 1) {
                seekAllToFrame(0);
            }
            isPlayingRef.current = true;
            setIsPlaying(true);
            playAllVideos();
            startLoop();
        }
    }, [seekAllToFrame, startLoop, stopLoop, playAllVideos, pauseAllVideos]);

    // Slider DRAG — pause once, then scrub as user drags
    const handleSeekDrag = useCallback((frame: number) => {
        if (!isDraggingRef.current) {
            isDraggingRef.current = true;
            wasPlayingBeforeDragRef.current = isPlayingRef.current;
            if (isPlayingRef.current) {
                isPlayingRef.current = false;
                stopLoop();
                pauseAllVideos();
            }
        }
        const clamped = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        currentFrameRef.current = clamped;
        updateOverlays(clamped);
        setCurrentFrame(clamped);
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
        playbackRateRef.current = rate;
        setPlaybackRate(rate);
        videoRefs.current.forEach((el) => { el.playbackRate = rate; });
    }, []);

    const handleSeekToStart = useCallback(() => {
        const wasPlaying = isPlayingRef.current;
        if (wasPlaying) { isPlayingRef.current = false; stopLoop(); pauseAllVideos(); }
        seekAllToFrame(0);
        if (wasPlaying) { isPlayingRef.current = true; setIsPlaying(true); playAllVideos(); startLoop(); }
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
    // Render
    // -----------------------------------------------------------------------
    if (videos.length === 0) {
        return (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary' }}>
                <Typography>{t("noVideosLoaded")}</Typography>
            </Box>
        );
    }

    const framePadLen = Math.max(String(totalFrames).length, 1);
    const initialFrameText = 'F' + String(currentFrame).padStart(framePadLen, '0');

    let initialTimeText: string;
    let timestampsAreReal = false;
    if (frameTimestamps) {
        const firstKey = Object.keys(frameTimestamps)[0];
        const camTs = firstKey ? frameTimestamps[firstKey] : null;
        if (camTs && currentFrame < camTs.length) {
            const realSec = camTs[currentFrame];
            initialTimeText = settings.timestampFormat === 'timecode'
                ? formatTimecodeFromSeconds(realSec, fps)
                : `${realSec.toFixed(3)}s`;
            timestampsAreReal = true;
        } else {
            initialTimeText = '~' + (settings.timestampFormat === 'timecode'
                ? formatTimecode(currentFrame, fps)
                : formatSeconds(currentFrame, fps));
        }
    } else {
        initialTimeText = '~' + (settings.timestampFormat === 'timecode'
            ? formatTimecode(currentFrame, fps)
            : formatSeconds(currentFrame, fps));
    }

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

                                {/* CAMERA ID — static */}
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
                                <Tooltip title={timestampsAreReal ? t("timestampFromRecording") : t("estimatedFromFrameNumber")} placement="top-end">
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
                    <Typography variant="caption">{t("loadingVideos", { ready: videosReady, total: videos.length })}</Typography>
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
