import React, {useState} from 'react';
import {
    Button,
    Stack,
    TextField,
    Typography,
    Switch,
    FormControlLabel,
    IconButton, InputAdornment,
} from '@mui/material';
import {startRecording, stopRecording} from "@/store/thunks/recording-thunks";
import Box from "@mui/material/Box";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {buildRecordingName, setRecordingInfo} from '@/store/slices/recordingInfoSlice';
import SettingsIcon from '@mui/icons-material/Settings';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import FolderOpenIcon from '@mui/icons-material/FolderOpen';


export const RecordingInfoPanel: React.FC = () => {
    const recordingInfo = useAppSelector(state => state.recordingStatus.currentRecordingInfo);
    const dispatch = useAppDispatch();
    const [recordingTag, setRecordingTag] = useState('');
    const [showSettings, setShowSettings] = useState(false);
    const handleSelectDirectory = async () => {
        try {
            const result = await window.electronAPI.selectDirectory();
            if (result) {
                dispatch(setRecordingInfo({ recordingDirectory: result }));
            }
        } catch (error) {
            console.error('Failed to select directory:', error);
        }
    };
    const currentRecordingName = buildRecordingName(
        recordingInfo.baseName,
        recordingInfo.useTimestamp,
        recordingInfo.useIncrement,
        recordingInfo.currentIncrement,
        recordingInfo.incrementFormat,
        recordingTag
    );

    const handleButtonClick = () => {
        if (recordingInfo.isRecording) {
            dispatch(stopRecording());
        } else {
            dispatch(startRecording(currentRecordingName));
        }
    };

    return (
        <Box sx={{ p: 2,
            m: 2,
            borderRadius: 1,
            borderStyle: 'solid',
            borderWidth:2,
            borderColor: extendedPaperbaseTheme.palette.primary.light,
            backgroundColor: extendedPaperbaseTheme.palette.primary.main }}>
            <Stack spacing={2}>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6">Recording Settings</Typography>
                    <IconButton onClick={() => setShowSettings(!showSettings)}>
                        <SettingsIcon
                            sx={{ color: showSettings ? extendedPaperbaseTheme.palette.primary.main : "#ccc" }}
                        />
                    </IconButton>
                </Box>

                <TextField
                    label="Recording Directory"
                    value={recordingInfo.recordingDirectory}
                    onChange={(e) => dispatch(setRecordingInfo({ recordingDirectory: e.target.value }))}
                    fullWidth
                    size="small"
                    InputProps={{
                        endAdornment: (
                            <InputAdornment position="end">
                                <IconButton
                                    onClick={handleSelectDirectory}
                                    edge="end"
                                >
                                    <FolderOpenIcon />
                                </IconButton>
                            </InputAdornment>
                        ),
                    }}
                />

                <Typography variant="body2">
                    Recording Name: {currentRecordingName}
                </Typography>

                {!recordingInfo.isRecording && (
                    <TextField
                        label="Recording Tag"
                        value={recordingTag}
                        onChange={(e) => setRecordingTag(e.target.value)}
                        size="small"
                        color="primary"
                        placeholder="Enter an optional tag"
                    />
                )}

                {/* Detailed Settings */}
                {showSettings && (
                    <Stack spacing={2} sx={{ pt: 1 }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={recordingInfo.useTimestamp}
                                    onChange={(e) => dispatch(setRecordingInfo({ useTimestamp: e.target.checked }))}
                                />
                            }
                            label="Use Timestamp"
                        />

                        {!recordingInfo.useTimestamp && (
                            <TextField
                                label="Base Name"
                                value={recordingInfo.baseName}
                                onChange={(e) => dispatch(setRecordingInfo({ baseName: e.target.value }))}
                                fullWidth
                                size="small"
                            />
                        )}

                        <FormControlLabel
                            control={
                                <Switch
                                    checked={recordingInfo.useIncrement}
                                    onChange={(e) => dispatch(setRecordingInfo({ useIncrement: e.target.checked }))}
                                />
                            }
                            label="Auto Increment"
                        />

                        {recordingInfo.useIncrement && (
                            <TextField
                                label="Increment Format (number of digits)"
                                value={recordingInfo.incrementFormat}
                                onChange={(e) => dispatch(setRecordingInfo({ incrementFormat: e.target.value }))}
                                type="number"
                                inputProps={{ min: 1, max: 10 }}
                                size="small"
                            />
                        )}
                    </Stack>
                )}

                <Button
                    onClick={handleButtonClick}
                    variant="contained"
                    color={recordingInfo.isRecording ? "error" : "secondary"}
                >
                    {recordingInfo.isRecording ? 'Stop Recording' : 'Start Recording'}
                </Button>
            </Stack>
        </Box>
    );
};
