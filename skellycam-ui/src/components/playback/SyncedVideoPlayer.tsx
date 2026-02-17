import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import { PlaybackControls } from './PlaybackControls';

interface VideoEntry {
    videoId: string;
    filename: string;
    streamUrl: string;
}

interface SyncedVideoPlayerProps {
    videos: VideoEntry[];
}

/**
 * Frame-locked multi-video player.
 *
 * Guarantees frame-perfect synchronization by NEVER calling .play() on any
 * video element. Instead, a single requestAnimationFrame loop maintains a
 * frame counter and sets `video.currentTime = frame / fps` on ALL videos
 * simultaneously each tick. The browser's video decoder handles seeking
 * to the correct frame internally.
 *
 * During "playback", the frame counter advances based on wall-clock elapsed
 * time × playbackRate. During pause, frame-step directly sets the counter.
 * All videos are always on the exact same frame number.
 */
export const SyncedVideoPlayer: React.FC<SyncedVideoPlayerProps> = ({ videos }) => {
    const theme = useTheme();
    const videoRefs = useRef<Map<string, HTMLVideoElement>>(new Map());

    // Playback state in refs for use inside the rAF loop (avoids stale closures)
    const isPlayingRef = useRef(false);
    const currentFrameRef = useRef(0);
    const totalFramesRef = useRef(0);
    const fpsRef = useRef(30);
    const playbackRateRef = useRef(1);
    const lastTickTimeRef = useRef<number | null>(null);
    const rafRef = useRef<number | null>(null);

    // React state for UI rendering
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentFrame, setCurrentFrame] = useState(0);
    const [totalFrames, setTotalFrames] = useState(0);
    const [fps, setFps] = useState(30);
    const [duration, setDuration] = useState(0);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [videosReady, setVideosReady] = useState(0);

    const allReady = videosReady >= videos.length;
    const columns = videos.length <= 1 ? 1 : videos.length <= 4 ? 2 : videos.length <= 9 ? 3 : 4;
    const currentTime = fpsRef.current > 0 ? currentFrameRef.current / fpsRef.current : 0;

    // -----------------------------------------------------------------------
    // Ref registration
    // -----------------------------------------------------------------------
    const setVideoRef = useCallback((videoId: string, el: HTMLVideoElement | null) => {
        if (el) {
            videoRefs.current.set(videoId, el);
        } else {
            videoRefs.current.delete(videoId);
        }
    }, []);

    // -----------------------------------------------------------------------
    // Core: seek ALL videos to a specific frame number
    // -----------------------------------------------------------------------
    const seekAllToFrame = useCallback((frame: number) => {
        const clampedFrame = Math.max(0, Math.min(frame, totalFramesRef.current - 1));
        const targetTime = fpsRef.current > 0 ? clampedFrame / fpsRef.current : 0;
        videoRefs.current.forEach((el) => {
            el.currentTime = targetTime;
        });
        currentFrameRef.current = clampedFrame;
        setCurrentFrame(clampedFrame);
    }, []);

    // -----------------------------------------------------------------------
    // The playback loop — single rAF drives all videos from one frame counter
    // -----------------------------------------------------------------------
    const tick = useCallback((timestamp: DOMHighResTimeStamp) => {
        if (!isPlayingRef.current) return;

        if (lastTickTimeRef.current !== null) {
            const deltaSeconds = (timestamp - lastTickTimeRef.current) / 1000;
            const frameAdvance = deltaSeconds * fpsRef.current * playbackRateRef.current;
            const newFrame = currentFrameRef.current + frameAdvance;

            if (newFrame >= totalFramesRef.current) {
                // Reached the end — stop
                seekAllToFrame(totalFramesRef.current - 1);
                isPlayingRef.current = false;
                lastTickTimeRef.current = null;
                setIsPlaying(false);
                return;
            }

            // Seek when we cross into a new integer frame
            const newIntFrame = Math.floor(newFrame);
            if (newIntFrame !== Math.floor(currentFrameRef.current)) {
                seekAllToFrame(newIntFrame);
            } else {
                // Accumulate fractional frame progress
                currentFrameRef.current = newFrame;
            }
        }

        lastTickTimeRef.current = timestamp;
        rafRef.current = requestAnimationFrame(tick);
    }, [seekAllToFrame]);

    const startLoop = useCallback(() => {
        lastTickTimeRef.current = null;
        rafRef.current = requestAnimationFrame(tick);
    }, [tick]);

    const stopLoop = useCallback(() => {
        if (rafRef.current !== null) {
            cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
        }
        lastTickTimeRef.current = null;
    }, []);

    useEffect(() => stopLoop, [stopLoop]);

    // -----------------------------------------------------------------------
    // Video metadata
    // -----------------------------------------------------------------------
    const handleLoadedMetadata = useCallback((e: React.SyntheticEvent<HTMLVideoElement>) => {
        const el = e.currentTarget;
        if (el.duration && el.duration !== Infinity) {
            const videoDuration = el.duration;
            setDuration((prev) => Math.max(prev, videoDuration));

            const estimatedFrames = Math.floor(videoDuration * fpsRef.current);
            if (totalFramesRef.current === 0 || estimatedFrames < totalFramesRef.current) {
                totalFramesRef.current = estimatedFrames;
                setTotalFrames(estimatedFrames);
            }
        }

        // Videos must NEVER auto-play — we drive them manually
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
            setIsPlaying(false);
            seekAllToFrame(Math.floor(currentFrameRef.current));
        } else {
            if (Math.floor(currentFrameRef.current) >= totalFramesRef.current - 1) {
                seekAllToFrame(0);
            }
            isPlayingRef.current = true;
            setIsPlaying(true);
            startLoop();
        }
    }, [seekAllToFrame, startLoop, stopLoop]);

    const handleSeek = useCallback((time: number) => {
        seekAllToFrame(Math.floor(time * fpsRef.current));
    }, [seekAllToFrame]);

    const handleFrameStep = useCallback((delta: number) => {
        if (isPlayingRef.current) {
            isPlayingRef.current = false;
            stopLoop();
            setIsPlaying(false);
        }
        seekAllToFrame(Math.floor(currentFrameRef.current) + delta);
    }, [seekAllToFrame, stopLoop]);

    const handlePlaybackRateChange = useCallback((rate: number) => {
        playbackRateRef.current = rate;
        setPlaybackRate(rate);
    }, []);

    const handleSeekToStart = useCallback(() => seekAllToFrame(0), [seekAllToFrame]);
    const handleSeekToEnd = useCallback(() => seekAllToFrame(totalFramesRef.current - 1), [seekAllToFrame]);

    // -----------------------------------------------------------------------
    // Keyboard shortcuts
    // -----------------------------------------------------------------------
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    handlePlayPause();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    handleFrameStep(e.shiftKey ? -10 : -1);
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    handleFrameStep(e.shiftKey ? 10 : 1);
                    break;
                case 'Home':
                    e.preventDefault();
                    handleSeekToStart();
                    break;
                case 'End':
                    e.preventDefault();
                    handleSeekToEnd();
                    break;
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
                <Typography>No videos loaded</Typography>
            </Box>
        );
    }

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
            {/* Video grid */}
            <Box
                sx={{
                    flex: 1,
                    display: 'grid',
                    gridTemplateColumns: `repeat(${columns}, 1fr)`,
                    gap: 0.5,
                    p: 0.5,
                    overflow: 'auto',
                    backgroundColor: theme.palette.mode === 'dark' ? '#111' : '#222',
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
                            minHeight: 150,
                        }}
                    >
                        <video
                            ref={(el) => setVideoRef(video.videoId, el)}
                            src={video.streamUrl}
                            preload="auto"
                            muted
                            playsInline
                            style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'contain',
                            }}
                            onLoadedMetadata={handleLoadedMetadata}
                        />
                        <Box
                            sx={{
                                position: 'absolute',
                                bottom: 8,
                                left: 8,
                                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                                color: '#fff',
                                px: 1,
                                py: 0.25,
                                borderRadius: 1,
                                fontSize: '12px',
                                fontFamily: 'monospace',
                            }}
                        >
                            {video.videoId}
                        </Box>
                    </Box>
                ))}
            </Box>

            {!allReady && (
                <Box sx={{ textAlign: 'center', py: 0.5, backgroundColor: theme.palette.warning.dark, color: '#fff' }}>
                    <Typography variant="caption">
                        Loading videos... ({videosReady}/{videos.length} ready)
                    </Typography>
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
                onPlayPause={handlePlayPause}
                onSeek={handleSeek}
                onFrameStep={handleFrameStep}
                onPlaybackRateChange={handlePlaybackRateChange}
                onSeekToStart={handleSeekToStart}
                onSeekToEnd={handleSeekToEnd}
            />
        </Box>
    );
};
