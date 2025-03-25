import React from 'react';
import {Button, Typography} from '@mui/material';

interface StartStopButtonProps {
    isRecording: boolean;
    countdown: number | null;
    onClick: () => void;
}

export const StartStopRecordingButton: React.FC<StartStopButtonProps> = ({
    isRecording,
    countdown,
    onClick
}) => {
    return (
        <>
            {countdown !== null && (
                <Typography variant="h4" align="center" color="secondary">
                    Starting in {countdown}...
                </Typography>
            )}
            <Button
                onClick={onClick}
                variant="contained"
                color={isRecording ? "error" : "secondary"}
                fullWidth
            >
                {isRecording ? 'Stop Recording' : 'Start Recording'}
            </Button>
        </>
    );
};