import React, { useEffect, useState } from 'react';
import clsx from 'clsx';
import { useTranslation } from 'react-i18next';

interface StartStopButtonProps {
    isRecording: boolean;
    isPending: boolean;
    countdown: number | null;
    recordingStartTime: number | null;
    disabled: boolean;
    onClick: () => void;
}

const formatDuration = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    const parts: string[] = [];
    if (hours > 0) parts.push(hours.toString().padStart(2, '0'));
    parts.push(minutes.toString().padStart(2, '0'));
    parts.push(secs.toString().padStart(2, '0'));
    return parts.join(':');
};

export const StartStopRecordingButton: React.FC<StartStopButtonProps> = ({
    isRecording, isPending, countdown, recordingStartTime, disabled, onClick,
}) => {
    const [recordingDuration, setRecordingDuration] = useState<number>(0);
    const { t } = useTranslation();

    useEffect(() => {
        if (!isRecording || !recordingStartTime || isPending) {
            setRecordingDuration(0);
            return;
        }
        const update = () => setRecordingDuration(Math.floor((Date.now() - recordingStartTime) / 1000));
        update();
        const interval = setInterval(update, 1000);
        return () => clearInterval(interval);
    }, [isRecording, recordingStartTime, isPending]);

    const isDisabled = disabled || isPending || countdown !== null;

    return (
        <button
            className={clsx(
                "record-button w-full",
                isRecording ? "record-button-active" : isPending ? "record-button-pending" : "record-button-idle",
            )}
            onClick={onClick}
            disabled={isDisabled}
        >
            {countdown !== null && countdown > 0 ? (
                <div className="flex items-center gap-1">
                    <span className="icon loader-icon icon-size-16" />
                    <p className="text bg text-white">{t('startingIn', { countdown })}</p>
                </div>
            ) : isPending ? (
                <div className="flex items-center gap-1">
                    <span className="icon loader-icon icon-size-16" />
                    <p className="text bg text-white">{isRecording ? t('stopping') : t('starting')}</p>
                </div>
            ) : isRecording ? (
                <div className="flex flex-col items-center gap-1">
                    <div className="flex items-center gap-1">
                        <span className="icon close-icon icon-size-16" />
                        <p className="text bg text-white">{t('stopRecordingButton')}</p>
                    </div>
                    <p className="record-button-duration">{formatDuration(recordingDuration)}</p>
                </div>
            ) : (
                <div className="flex items-center gap-1">
                    <span className="icon record-icon icon-size-16" />
                    <p className="text bg text-white">{t('startRecordingButton')}</p>
                </div>
            )}
        </button>
    );
};
