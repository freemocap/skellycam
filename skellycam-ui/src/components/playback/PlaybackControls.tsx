import React, { useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import DesignerCheckbox from '@/components/ui-components/Checkbox';
import type { PlaybackSettings } from './SyncedVideoPlayer';
import { useTranslation } from 'react-i18next';
import IconButton from '@/components/ui-components/IconButton';
import PromptTooltip from '@/components/ui-components/promptTooltip.tsx'


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

function formatTimecode(seconds: number, fps: number): string {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const frames = Math.floor((seconds % 1) * fps);

    return `${hrs.toString().padStart(2, '0')}:${mins
        .toString()
        .padStart(2, '0')}:${secs
        .toString()
        .padStart(2, '0')}:${frames
        .toString()
        .padStart(2, '0')}`;
}

function formatTimestamp(
    seconds: number,
    fps: number,
    format: 'seconds' | 'timecode'
): string {
    if (format === 'timecode') {
        return formatTimecode(seconds, fps);
    }

    return `${seconds.toFixed(3)}s`;
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
    const [settingsStyle, setSettingsStyle] = useState<React.CSSProperties>(
        {}
    );

    // Sync info panel
    const [syncInfoOpen, setSyncInfoOpen] = useState(true);

    const updateSetting = <
        K extends keyof PlaybackSettings
    >(
        key: K,
        value: PlaybackSettings[K]
    ) => {
        onSettingsChange({
            ...settings,
            [key]: value,
        });
    };

    const handleOpenSettings = () => {
        if (!settingsOpen && settingsButtonRef.current) {
            const rect =
                settingsButtonRef.current.getBoundingClientRect();

            setSettingsStyle({
                position: 'fixed',
                bottom: window.innerHeight - rect.top + 4,
                right: window.innerWidth - rect.right,
                zIndex: 200,
            });
        }

        setSettingsOpen((prev) => !prev);
    };

    // Timestamp segmented control options
    const timestampOptions = useMemo(
        () => [
            {
                label: '1.234s',
                value: 'seconds',
            },
            {
                label: 'HH:MM:SS:FF',
                value: 'timecode',
            },
        ],
        []
    );

    // Close settings popup on outside click
    useEffect(() => {
        if (!settingsOpen) return;

        const handleClick = (e: MouseEvent) => {
            if (
                settingsPopupRef.current &&
                !settingsPopupRef.current.contains(
                    e.target as Node
                ) &&
                settingsButtonRef.current &&
                !settingsButtonRef.current.contains(
                    e.target as Node
                )
            ) {
                setSettingsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClick);

        return () =>
            document.removeEventListener(
                'mousedown',
                handleClick
            );
    }, [settingsOpen]);

    return (
      <div className="playback-controls flex flex-col gap-2 px-2 py-1">
        {/* Timeline Scrubber */}
        <div className="playback-timeline-scrubber flex items-center gap-2 p-1 items-center">
          <div className="playback-timeline-track flex-1 relative">
            {/* Blue progress bar showing playhead position */}
            <div
              className="playback-timeline-progress"
              style={{
                width: `${
                  totalFrames > 0 ? (currentFrame / (totalFrames - 1)) * 100 : 0
                }%`,
              }}
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

            <div className="playback-timeline-frame-counter pos-abs z-2 text-white">
              Frame {currentFrame} / {totalFrames}
            </div>
            <span
              className="playback-timeline-start-time pos-abs z-2 text-white"
              title={t("estimatedTime")}
            >
              {formatTimestamp(currentTime, fps, settings.timestampFormat)}
            </span>
            <span
              className="playback-timeline-end-time pos-abs z-2 text-white"
              title={t("estimatedDuration")}
            >
              {formatTimestamp(duration, fps, settings.timestampFormat)}
            </span>
          </div>
        </div>

        {/* Transport Controls Row */}
        <div className="flex items-center justify-center">
          {/* Recording FPS Badge */}
          {recordingFps != null && recordingFps > 0 && (
            <span
              className="playback-fps-badge"
              title={t("recordingCaptureFps")}
            >
              rec: {recordingFps} fps
            </span>
          )}

          {/* Step & Skip Group */}
          <div className="playback-controls-group-step-skip bg-middark br-2 gap-1 flex flex-row p-1 items-center">
            <IconButton
              icon="skipbackward-icon"
              onClick={onSeekToStart}
              title={t("jumpToStart")}
              className="icon-size-28"
              tooltip={true}
              tooltipText={t("jumpToStart")}
              tooltipPosition="pos-top"
            />

            <IconButton
              icon="framebackward-icon"
              onClick={() => onFrameStep(-1)}
              title={t("previousFrame")}
              className="icon-size-28"
              tooltip={true}
              tooltipText={t("framebackward")}
              tooltipPosition="pos-top"
            />

            <IconButton
              icon={isPlaying ? "pause-icon" : "play-icon"}
              onClick={onPlayPause}
              title={isPlaying ? "Pause (Space)" : "Play (Space)"}
              className={clsx(
                "playback-btn-play",
                "icon-size-28",
                isPlaying && "playing",
              )}
              tooltip={true}
              tooltipText={isPlaying ? t("pause") : t("play")}
              tooltipPosition="pos-top"
            />

            <IconButton
              icon="frameforward-icon"
              onClick={() => onFrameStep(1)}
              title={t("nextFrame")}
              className="icon-size-28"
              tooltip={true}
              tooltipText={t("nextFrame")}
              tooltipPosition="pos-top"
            />

            <IconButton
              icon="skipforward-icon"
              onClick={onSeekToEnd}
              title={t("jumpToEnd")}
              className="icon-size-28"
              tooltip={true}
              tooltipText={t("jumpToEnd")}
              tooltipPosition="pos-top"
            />
          </div>

          {/* Loop & Speed Group */}
          <div className="playback-controls-group-loop-speed flex bg-middark br-2 flex-row p-1 gap-1">
            <IconButton
              icon="loop-icon"
              onClick={onToggleLoop}
              title={isLooping ? t("loopOn") : t("loopOff")}
              className={clsx("icon-size-28", isLooping && "activated")}
              tooltip={true}
              tooltipText={isLooping ? t("loopOn") : t("loopOff")}
              tooltipPosition="pos-top"
            />

            <select
              className="playback-speed-select"
              value={playbackRate}
              onChange={(e) => onPlaybackRateChange(Number(e.target.value))}
              title={t("playbackSpeed")}
            >
              {PLAYBACK_RATES.map((rate) => (
                <option key={rate} value={rate}>
                  {rate}×
                </option>
              ))}
            </select>
          </div>

          {/* Info & Settings Group */}
          <div className="playback-controls-group-info-settings flex items-center gap-1 flow-row p-1 bg-middark br-2">
                            <div className="flex pos-rel items-center onclick-tooltip-wrapper">
                <PromptTooltip
                    show={syncInfoOpen}
                    title="Recording Playback Timing Issue"
                    text={t("syncInfoTitle")}
                    position="pos-top"
                    variant="warning"
                    onClose={() => setSyncInfoOpen(false)}
                />

                <IconButton
                    icon="warning-icon"
                    onClick={() => setSyncInfoOpen((prev) => !prev)}
                    title={t("syncInfo")}
                    className={clsx("icon-size-28", syncInfoOpen && "activated")}
                    tooltip={true}
                    tooltipText={t("syncInfo")}
                    tooltipPosition="pos-top"
                />
                </div>

            <IconButton
              icon="settings-icon"
              ref={settingsButtonRef}
              onClick={handleOpenSettings}
              title={t("playbackSettings")}
              className={clsx("icon-size-28", settingsOpen && "activated")}
              tooltip={true}
              tooltipText={t("playbackSettings")}
              tooltipPosition="pos-top"
            />
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
              onChange={(e) => updateSetting("showOverlays", e.target.checked)}
            />

            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between">
                <p className="text sm text-gray">Timestamp format</p>

                <span className="text sm text-white">
                  {formatTimestamp(currentTime, fps, settings.timestampFormat)}
                </span>
              </div>

              <SegmentedControl
                options={timestampOptions}
                value={settings.timestampFormat}
                onChange={(val) =>
                  updateSetting(
                    "timestampFormat",
                    val as "seconds" | "timecode",
                  )
                }
                size="sm"
                className="segmented-control-sm gap-2"
              />
            </div>
          </div>
        )}

     
      </div>
    );
};