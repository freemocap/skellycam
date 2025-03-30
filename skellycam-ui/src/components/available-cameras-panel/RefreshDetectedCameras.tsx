// RefreshDetectedCameras.tsx
import React from 'react';
import {CircularProgress, IconButton} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import {useAppDispatch} from '@/store/AppStateStore';
import {detectBrowserDevices} from "@/store/thunks/detect-cameras-thunks";

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
