import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import DesignerCheckbox from '@/components/ui-components/Checkbox';
import type { PlaybackSettings } from './SyncedVideoPlayer';
import { useTranslation } from 'react-i18next';
import IconButton from '@/components/ui-components/IconButton';

interface PlaybackControlsProps {
    isPlaying: boolean;
    currentTime: number;
    duration: number;
    playbackRate: number;
    currentFrame: number;
    totalFrames: number;
    fps: number;
    recordingFps?: number;
    settings: PlaybackSettings;
    onSettingsChange: (settings: PlaybackSettings) => void;
    onPlayPause: () => void;
    onSeekDrag: (frame: number) => void;
    onSeekCommit: (frame: number) => void;
    onFrameStep: (delta: number) => void;
    onPlaybackRateChange: (rate: number) => void;
    onSeekToStart: () => void;
    onSeekToEnd: () => void;
    isLooping: boolean;
    onToggleLoop: () => void;
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
    recordingFps,
    settings,
    onSettingsChange,
    onPlayPause,
    onSeekDrag,
    onSeekCommit,
    onFrameStep,
    onPlaybackRateChange,
    onSeekToStart,
    onSeekToEnd,
    isLooping,
    onToggleLoop,
}) => {
    const { t } = useTranslation();

    // Settings popup
    const [settingsOpen, setSettingsOpen] = useState(false);
    const settingsButtonRef = useRef<HTMLButtonElement>(null);
    const settingsPopupRef = useRef<HTMLDivElement>(null);
    const [settingsStyle, setSettingsStyle] = useState<React.CSSProperties>({});

    // Sync info panel
    const [syncInfoOpen, setSyncInfoOpen] = useState(true);

    const updateSetting = <K extends keyof PlaybackSettings>(key: K, value: PlaybackSettings[K]) => {
        onSettingsChange({ ...settings, [key]: value });
    };

    const handleOpenSettings = () => {
        if (!settingsOpen && settingsButtonRef.current) {
            const rect = settingsButtonRef.current.getBoundingClientRect();
            setSettingsStyle({
                position: 'fixed',
                bottom: window.innerHeight - rect.top + 4,
                right: window.innerWidth - rect.right,
                zIndex: 200,
            });
        }
        setSettingsOpen((prev) => !prev);
    };

    // Close settings popup on outside click
    useEffect(() => {
        if (!settingsOpen) return;
        const handleClick = (e: MouseEvent) => {
            if (
                settingsPopupRef.current && !settingsPopupRef.current.contains(e.target as Node) &&
                settingsButtonRef.current && !settingsButtonRef.current.contains(e.target as Node)
            ) {
                setSettingsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
    }, [settingsOpen]);

    return (
        <div className="playback-controls flex flex-col gap-2 px-2 py-1">
            {/* Timeline Scrubber */}
            <div className="playback-timeline-scrubber flex items-center gap-2">
                <span className="playback-timeline-start-time" title={t('estimatedTime')}>
                    ~{formatTime(currentTime)}
                </span>

                <div className="playback-timeline-track flex-1 relative">
                    {/* Blue progress bar showing playhead position */}
                    <div 
                        className="playback-timeline-progress"
                        style={{ width: `${totalFrames > 0 ? (currentFrame / (totalFrames - 1)) * 100 : 0}%` }}
                    />
                    
                    <input
                        type="range"
                        dir="ltr"
                        className="playback-timeline-input"
                        min={0}
                        max={Math.max(totalFrames - 1, 1)}
                        step={1}
                        value={currentFrame}
                        onChange={(e) => onSeekDrag(Number(e.target.value))}
                        onMouseUp={(e) => onSeekCommit(Number(e.currentTarget.value))}
                        onTouchEnd={(e) => onSeekCommit(Number(e.currentTarget.value))}
                    />
                    
                    <div className="playback-timeline-frame-counter">
                        {currentFrame} / {totalFrames}
                    </div>
                </div>

                <span className="playback-timeline-end-time text-gray" title={t('estimatedDuration')}>
                    ~{formatTime(duration)}
                </span>
            </div>

            {/* Transport Controls Row */}
            <div className="flex items-center justify-center gap-2">
                {/* Recording FPS Badge - Left side */}
                {recordingFps != null && recordingFps > 0 && (
                    <span className="playback-fps-badge" title={t('recordingCaptureFps')}>
                        rec: {recordingFps} fps
                    </span>
                )}

                {/* Step & Skip Group */}
                <div className="playback-controls-group-step-skip flex items-center gap-1">
                    <IconButton
                        onClick={onSeekToStart}
                        title={t('jumpToStart')}
                        className="playback-btn-skip-back icon skipbackward-icon icon-size-20"
                    >
                    </IconButton>

                    <IconButton
                        onClick={() => onFrameStep(-1)}
                        title={t('previousFrame')}
                        className="playback-btn-frame-back icon framebackward-icon icon-size-20"
                    >
                    </IconButton>

                    <IconButton
                        onClick={onPlayPause}
                        title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
                        className={clsx('playback-btn-play icon icon-size-20', isPlaying ? 'pause-icon' : 'play-icon', isPlaying && 'playing')}
                    >
                    </IconButton>

                    <IconButton
                        onClick={() => onFrameStep(1)}
                        title={t('nextFrame')}
                        className="playback-btn-frame-forward icon frameforward-icon icon-size-20"
                    >
                    </IconButton>

                    <IconButton
                        onClick={onSeekToEnd}
                        title={t('jumpToEnd')}
                        className="playback-btn-skip-forward icon skipforward-icon icon-size-20"
                    >
                    </IconButton>
                </div>

                {/* Loop & Speed Group */}
                <div className="playback-controls-group-loop-speed flex items-center gap-1">
                    <IconButton
                        onClick={onToggleLoop}
                        title={isLooping ? t('loopOn') : t('loopOff')}
                        className={clsx('playback-btn-loop icon loop-icon icon-size-20', isLooping && 'activated')}
                    >
                    </IconButton>

                    <select
                        className="playback-speed-select"
                        value={playbackRate}
                        onChange={(e) => onPlaybackRateChange(Number(e.target.value))}
                        title={t('playbackSpeed')}
                    >
                        {PLAYBACK_RATES.map((rate) => (
                            <option key={rate} value={rate}>{rate}×</option>
                        ))}
                    </select>
                </div>

                {/* Info & Settings Group */}
                <div className="playback-controls-group-info-settings flex items-center gap-1">
                    <IconButton
                        onClick={() => setSyncInfoOpen((prev) => !prev)}
                        title={t('syncInfo')}
                        className={clsx('playback-btn-info icon warning-icon icon-size-20', syncInfoOpen && 'activated')}
                    >
                    </IconButton>

                    <IconButton
                        ref={settingsButtonRef}
                        onClick={handleOpenSettings}
                        title={t('playbackSettings')}
                        className={clsx('playback-btn-settings icon settings-icon icon-size-20', settingsOpen && 'activated')}
                    >
                    </IconButton>
                </div>
            </div>

            {/* Settings popup */}
            {settingsOpen && (
                <div
                    ref={settingsPopupRef}
                    className="playback-settings-popup bg-dark br-2 border-1 border-black elevated-sharp flex flex-col gap-2 p-2"
                    style={settingsStyle}
                >
                    <p className="text bg text-white">Display Settings</p>

                    <DesignerCheckbox
                        label="Show frame overlays"
                        checked={settings.showOverlays}
                        onChange={(e) => updateSetting('showOverlays', e.target.checked)}
                    />

                    <div className="flex flex-col gap-1">
                        <p className="text sm text-gray">Timestamp format</p>
                        <SegmentedControl
                            options={[
                                { label: '1.234s', value: 'seconds' },
                                { label: 'HH:MM:SS:FF', value: 'timecode' },
                            ]}
                            value={settings.timestampFormat}
                            onChange={(val) => updateSetting('timestampFormat', val as 'seconds' | 'timecode')}
                            size="sm"
                        />
                    </div>
                </div>
            )}

            {/* Sync info panel */}
            {syncInfoOpen && (
                <div className="playback-sync-info">
                    <p className="text sm playback-sync-title">{t('syncInfoTitle')}</p>
                </div>
            )}
        </div>
    );
};
