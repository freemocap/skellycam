import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import DesignerCheckbox from '@/components/ui-components/Checkbox';
import type { PlaybackSettings } from './SyncedVideoPlayer';
import { useTranslation } from 'react-i18next';

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
        <div className="playback-controls flex flex-col gap-1 px-2 py-1">
            {/* Seek slider row */}
            <div className="flex items-center gap-2">
                <span
                    className="playback-timecode"
                    title={t('estimatedTime')}
                >
                    ~{formatTime(currentTime)}
                </span>

                <input
                    type="range"
                    dir="ltr"
                    className="playback-slider flex-1"
                    min={0}
                    max={Math.max(totalFrames - 1, 1)}
                    step={1}
                    value={currentFrame}
                    onChange={(e) => onSeekDrag(Number(e.target.value))}
                    onMouseUp={(e) => onSeekCommit(Number(e.currentTarget.value))}
                    onTouchEnd={(e) => onSeekCommit(Number(e.currentTarget.value))}
                />

                <span
                    className="playback-timecode text-gray"
                    title={t('estimatedDuration')}
                >
                    ~{formatTime(duration)}
                </span>
            </div>

            {/* Transport row */}
            <div className="flex items-center justify-center gap-1">
                {/* Left: frame info */}
                <div className="flex items-center gap-2 playback-info-left">
                    <span className="playback-frame-badge" title="Current frame">
                        Frame {currentFrame} / {totalFrames}
                    </span>
                    {recordingFps != null && recordingFps > 0 && (
                        <span className="playback-fps-badge" title={t('recordingCaptureFps')}>
                            rec: {recordingFps} fps
                        </span>
                    )}
                </div>

                {/* Center: transport buttons */}
                <button className="button icon-button playback-transport" onClick={onSeekToStart} title={t('jumpToStart')}>⏮</button>
                <button className="button icon-button playback-transport" onClick={() => onFrameStep(-1)} title={t('previousFrame')}>◀</button>

                <button
                    className={clsx('button icon-button playback-play-btn', isPlaying && 'playing')}
                    onClick={onPlayPause}
                    title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
                >
                    {isPlaying ? '⏸' : '▶'}
                </button>

                <button className="button icon-button playback-transport" onClick={() => onFrameStep(1)} title={t('nextFrame')}>▶</button>
                <button className="button icon-button playback-transport" onClick={onSeekToEnd} title={t('jumpToEnd')}>⏭</button>

                <button
                    className={clsx('button icon-button playback-transport', isLooping && 'activated')}
                    onClick={onToggleLoop}
                    title={isLooping ? t('loopOn') : t('loopOff')}
                >
                    ↺
                </button>

                {/* Right: speed + settings */}
                <div className="flex items-center gap-1 playback-info-right">
                    <span className="text sm text-gray">Speed:</span>
                    <select
                        className="sort-select input-field"
                        value={playbackRate}
                        onChange={(e) => onPlaybackRateChange(Number(e.target.value))}
                        title={t('playbackSpeed')}
                    >
                        {PLAYBACK_RATES.map((rate) => (
                            <option key={rate} value={rate}>{rate}×</option>
                        ))}
                    </select>

                    <button
                        className={clsx('button icon-button playback-transport', syncInfoOpen && 'activated')}
                        onClick={() => setSyncInfoOpen((prev) => !prev)}
                        title={t('syncInfo')}
                    >
                        ℹ
                    </button>

                    <button
                        ref={settingsButtonRef}
                        className={clsx('button icon-button playback-transport', settingsOpen && 'activated')}
                        onClick={handleOpenSettings}
                        title={t('playbackSettings')}
                    >
                        ⚙
                    </button>
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
