import React from 'react';
import { DelayRecordingStartControl } from "@/components/recording-info-panel/recording-subcomponents/DelayRecordingStartControl";
import { BaseRecordingDirectoryInput } from "@/components/recording-info-panel/recording-subcomponents/BaseRecordingDirectoryInput";
import { RecordingNamePreview } from "@/components/recording-info-panel/recording-subcomponents/RecordingNamePreview";
import { RecordingSettingsSection } from "@/components/recording-info-panel/recording-subcomponents/RecordingSettingsSection";

interface RecordingControlsSectionProps {
    recordingDirectory: string;
    recordingName: string;
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

export const RecordingControlsSection: React.FC<RecordingControlsSectionProps> = (props) => {
    const {
        recordingDirectory, recordingName, recordingTag,
        useDelayStart, delaySeconds, useTimestamp, baseName,
        useIncrement, currentIncrement, createSubfolder, customSubfolderName,
        isRecording, onDelayToggle, onDelayChange, onTagChange,
        onUseTimestampChange, onBaseNameChange, onUseIncrementChange,
        onIncrementChange, onCreateSubfolderChange, onCustomSubfolderNameChange,
    } = props;

    return (
        <div className="flex flex-col gap-2 p-2 pl-3">
            <DelayRecordingStartControl
                useDelay={useDelayStart}
                delaySeconds={delaySeconds}
                onDelayToggle={onDelayToggle}
                onDelayChange={onDelayChange}
            />
            <BaseRecordingDirectoryInput value={recordingDirectory} />
            <RecordingNamePreview
                name={recordingName}
                tag={recordingTag}
                isRecording={isRecording}
                onTagChange={onTagChange}
            />
            <RecordingSettingsSection
                useTimestamp={useTimestamp}
                baseName={baseName}
                useIncrement={useIncrement}
                currentIncrement={currentIncrement}
                createSubfolder={createSubfolder}
                customSubfolderName={customSubfolderName}
                onUseTimestampChange={onUseTimestampChange}
                onBaseNameChange={onBaseNameChange}
                onUseIncrementChange={onUseIncrementChange}
                onIncrementChange={onIncrementChange}
                onCreateSubfolderChange={onCreateSubfolderChange}
                onCustomSubfolderNameChange={onCustomSubfolderNameChange}
            />
        </div>
    );
};
