// RefreshDetectedCameras.tsx
import React from 'react';
import { IconButton, CircularProgress } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAppDispatch } from '@/store/AppStateStore';
import { detectBrowserDevices } from '@/store/thunks/camera-thunks';

interface RefreshDetectedCamerasButtonProps {
    isLoading: boolean;
}

export const RefreshDetectedCamerasButton: React.FC<RefreshDetectedCamerasButtonProps> = ({ isLoading }) => {
    const dispatch = useAppDispatch();

    const handleRefresh = () => {
        if (!isLoading) {
            dispatch(detectBrowserDevices(true));
        }
    };

    return (
        <IconButton
            color="inherit"
            onClick={handleRefresh}
            disabled={isLoading}
        >
            {isLoading ? (
                <CircularProgress size={24} color="inherit" />
            ) : (
                <RefreshIcon />
            )}
        </IconButton>
    );
};
