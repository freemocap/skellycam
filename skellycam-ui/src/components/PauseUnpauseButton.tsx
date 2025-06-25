// skellycam-ui/src/components/PauseUnpauseButton.tsx
import React, { useState } from 'react';
import { Button, keyframes, CircularProgress } from '@mui/material';
import { styled } from '@mui/system';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';

interface PauseUnpauseButtonProps {
    disabled?: boolean;
}

const pulseAnimation = keyframes`
    0% {
        background-color: rgba(25, 118, 210, 0.8);
    }
    50% {
        background-color: rgba(25, 118, 210, 1);
    }
    100% {
        background-color: rgba(25, 118, 210, 0.8);
    }
`;

const PulsingButton = styled(Button)(({ pulsing }: { pulsing: boolean }) => ({
    backgroundColor: '#1976d2', // MUI primary blue
    borderRadius: '8px',
    padding: '10px 16px',
    '&:hover': {
        backgroundColor: '#1565c0', // Darker blue on hover
    },
    ...(pulsing && {
        animation: `${pulseAnimation} 1.5s infinite ease-in-out`,
    }),
}));

export const PauseUnpauseButton: React.FC<PauseUnpauseButtonProps> = ({
                                                                          disabled = false
                                                                      }) => {
    const [isPaused, setIsPaused] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    const handlePause = async () => {
        setIsLoading(true);
        try {
            console.log('Pausing...');
            const pauseUrl = 'http://localhost:8006/skellycam/camera/group/all/pause';
            const response = await fetch(pauseUrl, {
                method: 'GET',
            });

            if (response.ok) {
                console.log('Paused successfully');
                setIsPaused(true);
            } else {
                console.error(`Failed to Pause: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Pause failed:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleUnpause = async () => {
        setIsLoading(true);
        try {
            console.log('Unpausing...');
            const unpauseUrl = 'http://localhost:8006/skellycam/camera/group/all/unpause';
            const response = await fetch(unpauseUrl, {
                method: 'GET',
            });

            if (response.ok) {
                console.log('Unpaused successfully');
                setIsPaused(false);
            } else {
                console.error(`Failed to unpause: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Unpause failed:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleClick = () => {
        if (isPaused) {
            handleUnpause();
        } else {
            handlePause();
        }
    };

    return (
        <PulsingButton
            onClick={handleClick}
            variant="contained"
            pulsing={isPaused}
            fullWidth
            disabled={disabled || isLoading}
            startIcon={isLoading ? undefined : isPaused ? <PlayArrowIcon /> : <PauseIcon />}
        >
            {isLoading ? <CircularProgress size={24} color="inherit" /> : (isPaused ? 'Resume' : 'Pause')}
        </PulsingButton>
    );
};
