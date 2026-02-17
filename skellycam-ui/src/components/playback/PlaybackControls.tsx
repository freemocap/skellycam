import React from 'react';
import {
    Box,
    IconButton,
    Slider,
    Typography,
    Select,
    MenuItem,
    Tooltip,
    useTheme,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import FirstPageIcon from '@mui/icons-material/FirstPage';
import LastPageIcon from '@mui/icons-material/LastPage';

interface PlaybackControlsProps {
    isPlaying: boolean;
    currentTime: number;
    duration: number;
    playbackRate: number;
    currentFrame: number;
    totalFrames: number;
    fps: number;
    onPlayPause: () => void;
    onSeek: (time: number) => void;
    onFrameStep: (delta: number) => void;
    onPlaybackRateChange: (rate: number) => void;
    onSeekToStart: () => void;
    onSeekToEnd: () => void;
}

const PLAYBACK_RATES = [0.1, 0.25, 0.5, 1, 1.5, 2, 4, 8];

function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 100);
    return `${mins}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
    isPlaying,
    currentTime,
    duration,
    playbackRate,
    currentFrame,
    totalFrames,
    fps,
    onPlayPause,
    onSeek,
    onFrameStep,
    onPlaybackRateChange,
    onSeekToStart,
    onSeekToEnd,
}) => {
    const theme = useTheme();

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5,
                px: 2,
                py: 1,
                backgroundColor: theme.palette.background.paper,
                borderTop: `1px solid ${theme.palette.divider}`,
            }}
        >
            {/* Timeline slider */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Typography variant="caption" sx={{ fontFamily: 'monospace', minWidth: 70, textAlign: 'right' }}>
                    {formatTime(currentTime)}
                </Typography>
                <Slider
                    value={currentTime}
                    min={0}
                    max={duration || 1}
                    step={0.001}
                    onChange={(_, value) => onSeek(value as number)}
                    sx={{ flex: 1 }}
                    size="small"
                />
                <Typography variant="caption" sx={{ fontFamily: 'monospace', minWidth: 70 }}>
                    {formatTime(duration)}
                </Typography>
            </Box>

            {/* Transport controls */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                {/* Left: frame info */}
                <Typography
                    variant="caption"
                    sx={{ fontFamily: 'monospace', minWidth: 140, textAlign: 'right', mr: 2, color: theme.palette.text.secondary }}
                >
                    Frame {currentFrame} / {totalFrames} ({fps > 0 ? `${fps.toFixed(1)} fps` : '? fps'})
                </Typography>

                {/* Center: transport buttons */}
                <Tooltip title="Jump to start">
                    <IconButton size="small" onClick={onSeekToStart}>
                        <FirstPageIcon />
                    </IconButton>
                </Tooltip>

                <Tooltip title="Previous frame (←)">
                    <IconButton size="small" onClick={() => onFrameStep(-1)}>
                        <SkipPreviousIcon />
                    </IconButton>
                </Tooltip>

                <Tooltip title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}>
                    <IconButton onClick={onPlayPause} color="primary" sx={{ mx: 1 }}>
                        {isPlaying ? <PauseIcon fontSize="large" /> : <PlayArrowIcon fontSize="large" />}
                    </IconButton>
                </Tooltip>

                <Tooltip title="Next frame (→)">
                    <IconButton size="small" onClick={() => onFrameStep(1)}>
                        <SkipNextIcon />
                    </IconButton>
                </Tooltip>

                <Tooltip title="Jump to end">
                    <IconButton size="small" onClick={onSeekToEnd}>
                        <LastPageIcon />
                    </IconButton>
                </Tooltip>

                {/* Right: speed selector */}
                <Box sx={{ display: 'flex', alignItems: 'center', ml: 2, gap: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">Speed:</Typography>
                    <Select
                        value={playbackRate}
                        onChange={(e) => onPlaybackRateChange(Number(e.target.value))}
                        size="small"
                        variant="outlined"
                        sx={{ minWidth: 70, '& .MuiSelect-select': { py: 0.25, fontSize: '0.8rem' } }}
                    >
                        {PLAYBACK_RATES.map((rate) => (
                            <MenuItem key={rate} value={rate}>
                                {rate}×
                            </MenuItem>
                        ))}
                    </Select>
                </Box>
            </Box>
        </Box>
    );
};
