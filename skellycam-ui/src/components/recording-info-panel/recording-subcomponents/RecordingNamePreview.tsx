import React from 'react';
import { useTranslation } from 'react-i18next';
import TextSelector from '@/components/ui-components/TextSelector';

interface RecordingNamePreviewProps {
    name: string;
    tag: string;
    isRecording: boolean;
    onTagChange: (tag: string) => void;
}

export const RecordingNamePreview: React.FC<RecordingNamePreviewProps> = ({
    name, tag, isRecording, onTagChange,
}) => {
    const { t } = useTranslation();
    return (
        <div className="flex flex-col gap-1">
            <p className="text sm text-gray">{t('recordingName', { name })}</p>
            {!isRecording && (
                <TextSelector
                    value={tag}
                    onChange={onTagChange}
                    placeholder={t("recordingTagPlaceholder")}
                />
            )}
        </div>
    );
};
