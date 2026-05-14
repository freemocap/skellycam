import React, { useEffect } from 'react';
import useDraggableTooltips from '@/hooks/useDraggableTooltips';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import { RecordingPathTreeItem } from './RecordingPathTreeItem';

interface RecordingPathModalProps {
    open: boolean;
    onClose: () => void;
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
    onNameChange: (value: string) => void;
    onUseTimestampChange: (value: boolean) => void;
    onBaseNameChange: (value: string) => void;
    onUseIncrementChange: (value: boolean) => void;
    onIncrementChange: (value: number) => void;
    onCreateSubfolderChange: (value: boolean) => void;
    onCustomSubfolderNameChange: (value: string) => void;
}

export const RecordingPathModal: React.FC<RecordingPathModalProps> = ({ open, onClose, ...itemProps }) => {
    useDraggableTooltips();

    useEffect(() => {
        if (!open) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            className="recording-path-modal overlay splash-overlay inset-0 reveal fadeIn"
            style={{ position: 'fixed', zIndex: 50 }}
            onClick={onClose}
        >
            <div
                className="draggable bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-2 gap-2"
                style={{ minWidth: 380, maxWidth: 520, maxHeight: '80vh', overflowY: 'auto' }}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex justify-content-space-between items-center">
                    <SubactionHeader text="Recording Path &amp; Settings" />
                    <button className="button icon-button" onClick={onClose}>
                        <span className="icon close-icon icon-size-16" />
                    </button>
                </div>

                <RecordingPathTreeItem {...itemProps} />
            </div>
        </div>
    );
};
