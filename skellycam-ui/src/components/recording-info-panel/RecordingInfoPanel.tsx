import React, {useEffect, useState} from 'react';
import {Box, IconButton, Stack} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {
    RecordingSettingsSection
} from "@/components/recording-info-panel/recording-subcomponents/RecordingSettingsSection";
import {
    StartStopRecordingButton
} from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import {DelayRecordingStartControl} from "@/components/recording-info-panel/recording-subcomponents/DelayRecordingStartControl";
import {
    FullRecordingPathPreview
} from "@/components/recording-info-panel/recording-subcomponents/FullRecordingPathPreview";
import {
    BaseRecordingDirectoryInput
} from "@/components/recording-info-panel/recording-subcomponents/BaseRecordingDirectoryInput";
import {RecordingNamePreview} from "@/components/recording-info-panel/recording-subcomponents/RecordingNamePreview";
import {startRecording, stopRecording} from "@/store/thunks/start-stop-recording-thunks";

export const RecordingInfoPanel: React.FC = () => {
    const dispatch = useAppDispatch();
    const recordingInfo = useAppSelector(state => state.recordingStatus.currentRecordingInfo);

    // Local UI state
    const [showSettings, setShowSettings] = useState(false);
    const [createSubfolder, setCreateSubfolder] = useState(true);
    const [useDelayStart, setUseDelayStart] = useState(true);
    const [delaySeconds, setDelaySeconds] = useState(3);
    const [countdown, setCountdown] = useState<number | null>(null);
    const [recordingTag, setRecordingTag] = useState('');

    // Local recording naming preferences
    const [useTimestamp, setUseTimestamp] = useState(true);
    const [useIncrement, setUseIncrement] = useState(false);
    const [currentIncrement, setCurrentIncrement] = useState(1);
    const [baseName, setBaseName] = useState('recording');
    const [customSubfolderName, setCustomSubfolderName] = useState('');

    // Handle countdown timer
    useEffect(() => {
        if (countdown !== null && countdown > 0) {
            const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
            return () => clearTimeout(timer);
        } else if (countdown === 0) {
            handleStartRecording();
            setCountdown(null);
        }
    }, [countdown]);

    const getTimestampString = (): string => {
        const now = new Date();
        return now.toISOString()
            .replace(/[:.]/g, '-')
            .replace('T', '_')
            .split('.')[0];
    };

    const buildRecordingName = (): string => {
        const parts: string[] = [];

        // Base name component
        if (useTimestamp) {
            parts.push(getTimestampString());
        } else {
            parts.push(baseName);
        }

        // Add tag if present
        if (recordingTag) {
            parts.push(recordingTag);
        }

        // Add increment if enabled
        if (useIncrement) {
            parts.push(currentIncrement.toString().padStart(3, '0'));
        }

        return parts.join('_');
    };
    const getFullRecordingPath = (): string => {
        const recordingName = buildRecordingName();
        if (!createSubfolder) {
            return `${recordingInfo.recordingDirectory}/${recordingName}`;
        }

        const subfolderName = customSubfolderName || getTimestampString();
        return `${recordingInfo.recordingDirectory}/${subfolderName}/${recordingName}`;
    };

    const handleStartRecording = () => {
        console.log('Starting recording...');

        const recordingName = buildRecordingName();
        const subfolderName = createSubfolder ? (customSubfolderName || getTimestampString()) : '';
        const recordingPath = createSubfolder
            ? `${recordingInfo.recordingDirectory}/${subfolderName}`
            : recordingInfo.recordingDirectory;

        console.log('Recording path:', recordingPath);
        console.log('Recording name:', recordingName);

        if (useIncrement) {
            setCurrentIncrement(prev => prev + 1);
        }

        dispatch(startRecording({
            recordingName,
            recordingDirectory: recordingPath
        }));
    };
    const handleButtonClick = () => {
        if (recordingInfo.isRecording) {
            console.log('Stopping recording...');
            dispatch(stopRecording());
        } else if (useDelayStart) {
            console.log(`Starting countdown from ${delaySeconds} seconds`);
            setCountdown(delaySeconds);
        } else {
            handleStartRecording();
        }
    };

    return (
        <Box sx={{
            p: 2,
            m: 2,
            borderRadius: 1,
            borderStyle: 'solid',
            borderWidth: 2,
            borderColor: extendedPaperbaseTheme.palette.primary.light,
            backgroundColor: extendedPaperbaseTheme.palette.primary.light
        }}>
            <Stack spacing={2}>
                {/* Controls Bar - Always Visible */}
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <StartStopRecordingButton
                        isRecording={recordingInfo.isRecording}
                        countdown={countdown}
                        onClick={handleButtonClick}
                    />
                    <IconButton onClick={() => setShowSettings(!showSettings)}>
                        <SettingsIcon
                            sx={{color: showSettings ? extendedPaperbaseTheme.palette.primary.main : "#ccc"}}
                        />
                    </IconButton>
                </Box>

                {/* Settings Panel */}
                {showSettings && (
                    <>
                        <DelayRecordingStartControl
                            useDelay={useDelayStart}
                            delaySeconds={delaySeconds}
                            onDelayToggle={setUseDelayStart}
                            onDelayChange={setDelaySeconds}
                        />
                        <FullRecordingPathPreview
                            directory={recordingInfo.recordingDirectory}
                            filename={buildRecordingName()}
                            subfolder={createSubfolder ? (customSubfolderName || getTimestampString()) : undefined}
                        />
                        <BaseRecordingDirectoryInput
                            value={recordingInfo.recordingDirectory}
                        />
                        <RecordingNamePreview
                            name={buildRecordingName()}
                            tag={recordingTag}
                            isRecording={recordingInfo.isRecording}
                            onTagChange={setRecordingTag}
                        />
                        <RecordingSettingsSection
                            useTimestamp={useTimestamp}
                            baseName={baseName}
                            useIncrement={useIncrement}
                            currentIncrement={currentIncrement}
                            createSubfolder={createSubfolder}
                            customSubfolderName={customSubfolderName}
                            onUseTimestampChange={setUseTimestamp}
                            onBaseNameChange={setBaseName}
                            onUseIncrementChange={setUseIncrement}
                            onIncrementChange={setCurrentIncrement}
                            onCreateSubfolderChange={setCreateSubfolder}
                            onCustomSubfolderNameChange={setCustomSubfolderName}
                        />
                    </>
                )}
            </Stack>
        </Box>
    );
};
