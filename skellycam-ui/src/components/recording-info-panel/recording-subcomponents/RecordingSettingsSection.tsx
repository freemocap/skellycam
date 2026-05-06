import React from 'react';
import { useTranslation } from 'react-i18next';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import TextSelector from '@/components/ui-components/TextSelector';
import ValueSelector from '@/components/ui-components/ValueSelector';

interface RecordingSettingsProps {
    useTimestamp: boolean;
    baseName: string;
    useIncrement: boolean;
    currentIncrement: number;
    createSubfolder: boolean;
    customSubfolderName: string;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingSettingsSection: React.FC<RecordingSettingsProps> = ({
    useTimestamp, baseName, useIncrement, currentIncrement,
    createSubfolder, customSubfolderName,
    onUseTimestampChange, onBaseNameChange, onUseIncrementChange, onIncrementChange,
    onCreateSubfolderChange, onCustomSubfolderNameChange,
}) => {
    const { t } = useTranslation();

    return (
        <div className="flex flex-col gap-1 bg-middark br-1 p-1">
            <SubactionHeader text={t('recordingSettings')} />

            {/* Timestamp toggle + base name input */}
            <div className="flex items-center gap-1">
                <ToggleComponent
                    text={t("timestamp")}
                    isToggled={useTimestamp}
                    onToggle={onUseTimestampChange}
                />
                {!useTimestamp && (
                    <TextSelector
                        value={baseName}
                        onChange={onBaseNameChange}
                        placeholder={t("baseName")}
                    />
                )}
            </div>

            {/* Subfolder toggle + name input */}
            <div className="flex items-center gap-1">
                <ToggleComponent
                    text={t("subfolder")}
                    isToggled={createSubfolder}
                    onToggle={onCreateSubfolderChange}
                />
                {createSubfolder && (
                    <TextSelector
                        value={customSubfolderName}
                        onChange={onCustomSubfolderNameChange}
                        placeholder={t("subfolderPlaceholder")}
                    />
                )}
            </div>

            {/* Auto-increment toggle + number */}
            <div className="flex items-center gap-1">
                <ToggleComponent
                    text={t("increment")}
                    isToggled={useIncrement}
                    onToggle={onUseIncrementChange}
                />
                {useIncrement && (
                    <ValueSelector
                        value={currentIncrement}
                        min={1}
                        max={9999}
                        unit=""
                        onChange={onIncrementChange}
                    />
                )}
            </div>
        </div>
    );
};
