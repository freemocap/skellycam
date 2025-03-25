import React, {useEffect, useState} from 'react';
import {Button, Stack, TextField, Typography} from '@mui/material';
import {getTimestampRecordingName, startRecording, stopRecording} from "@/store/thunks/recording-thunks";
import Box from "@mui/material/Box";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";

export const RecordingPanel: React.FC = () => {
    const recordingInfo = useAppSelector(state => state.recordingStatus.currentRecordingInfo);
    const isRecording = recordingInfo?.isRecording ?? false;
    const dispatch = useAppDispatch();
    const [recordingTag, setRecordingTag] = useState('');
    const [timestampRecordingName, setTimestampRecordingName] = useState(getTimestampRecordingName());

    const recordingFullName = `${timestampRecordingName}${recordingTag ? `_${recordingTag}` : ''}`

    // Update the timestamp every second when not recording
    useEffect(() => {
        if (!isRecording) {
            const interval = setInterval(() => {
                setTimestampRecordingName(getTimestampRecordingName());
            }, 1000);
            return () => clearInterval(interval);
        }
    }, [isRecording]);

    const handleButtonClick = () => {
        if (isRecording) {
            dispatch(stopRecording());
        } else {
            dispatch(startRecording(recordingFullName));
        }
    };
    return (
        <Box sx={{ p: 2, m:2, border: '1px solid #ccc', color: '#333', backgroundColor: '#f9f9f9'}}>
            <Stack spacing={2}>
                <Typography variant="body2" color="text.primary">
                    Recording Name:<br/>{`${timestampRecordingName}${recordingTag ? `_${recordingTag}` : ''}`}
                </Typography>

                {!isRecording && (
                    <TextField
                        label="Recording Tag"
                        value={recordingTag}
                        onChange={(e) => setRecordingTag(e.target.value)}
                        size="small"
                        placeholder="Enter an optional tag"
                        disabled={isRecording}
                        helperText="Add a tag to the recording name"
                    />
                )}

                {isRecording && recordingInfo?.recordingTag && (
                    <Typography variant="body2" color="text.primary">
                        Current Recording: {recordingInfo.recordingTag}
                    </Typography>
                )}

                <Button
                    onClick={handleButtonClick}
                    sx={{
                        backgroundColor: isRecording ? 'red' : 'blue',
                        color: '#aaa',
                        fontSize: '16px',
                        padding: '10px 20px',
                        borderRadius: '8px',
                        '&:hover': {
                            backgroundColor: isRecording ? '#d32f2f' : '#1976d2',
                        },
                    }}
                >
                    {isRecording ? 'Stop Recording' : 'Start Recording'}
                </Button>
            </Stack>
        </Box>
    );
};
