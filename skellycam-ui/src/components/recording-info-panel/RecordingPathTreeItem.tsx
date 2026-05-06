import React from 'react';
import { FullRecordingPathPreview } from "@/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview";
import { RecordingControlsSection } from "@/components/recording-info-panel/RecordingControlsTreeSection";

interface RecordingPathTreeItemProps {
    recordingDirectory: string;
    recordingName: string;
    subfolder?: string;
    countdown: number | null;
    recordingTag: string;
    useDelayStart: boolean;
    delaySeconds: number;
    useTimestamp: boolean;
    baseName: string;
    useIncrement: boolean;
    currentIncrement: number;
    createSubfolder: boolean;
    customSubfolderName: string;
    isRecording: boolean;
    onDelayToggle: (value: boolean) => void;
    onDelayChange: (value: number) => void;
    onTagChange: (value: string) => void;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingPathTreeItem: React.FC<RecordingPathTreeItemProps> = ({
    recordingDirectory, recordingName, subfolder, countdown, ...controlProps
}) => {
    return (
        <div className="flex flex-col gap-1" onKeyDown={(e) => e.stopPropagation()}>
            <FullRecordingPathPreview
                directory={recordingDirectory}
                filename={recordingName}
                subfolder={subfolder}
            />

            {countdown !== null && (
                <p className="recording-countdown">{`Starting in ${countdown}...`}</p>
            )}

            <RecordingControlsSection
                recordingDirectory={recordingDirectory}
                recordingName={recordingName}
                {...controlProps}
            />
        </div>
    );
};
