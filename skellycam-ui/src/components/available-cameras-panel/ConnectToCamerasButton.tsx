// ConnectToCamerasButton.tsx
import React from 'react';
import {Button, CircularProgress, Tooltip, Typography} from '@mui/material';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {useAppDispatch, useAppSelector} from "@/store";
import {selectSelectedDevices} from "@/store/slices/cameras/camerasSlice";
import {connectToCameras} from "@/store/slices/cameras/old-camera-thunks/connect-to-cameras-thunk";
import SystemUpdateAltIcon from "@mui/icons-material/SystemUpdateAlt";
import {useNavigate} from "react-router-dom";

interface ConnectToCamerasButtonProps {
    onClick?: () => void;
}

export const ConnectToCamerasButton: React.FC<ConnectToCamerasButtonProps> = ({onClick}) => {
    const dispatch = useAppDispatch();
    const isLoading = useAppSelector(state => state.cameras.isLoading);
    const selectedCameras = useAppSelector(selectSelectedDevices);
    const navigate = useNavigate()

    const handleConnectClick = async () => {
        console.log("ConnectToCamerasButton handleConnectClick", selectedCameras, isLoading);
        navigate('/cameras')
        if (isLoading) {
            console.log('Camera connection is already in progress');
            return;
        }

        try {
            if (selectedCameras && selectedCameras.length > 0) {
                // If we have an onClick prop, use that (for testing/custom handling)
                if (onClick) {
                    onClick();
                } else {
                    // Otherwise dispatch the thunk which will get the configs from state
                    await dispatch(connectToCameras()).unwrap();
                    console.log('Connected to selected cameras');
                }
            } else {
                console.log('No cameras selected to connect to');
            }
        } catch (error) {
            console.error('Error connecting to cameras:', error);
        }
    };

    const hasSelectedCameras = selectedCameras.length > 0;

    return (
        <Tooltip title="Create new Camera Group  with these settings or update camera configurations of existing group" arrow>
        <Button
            variant="contained"
            onClick={handleConnectClick}
            disabled={!hasSelectedCameras || isLoading}
            sx={{
                ml: 1,
                fontSize: 'small',
                color: extendedPaperbaseTheme.palette.primary.contrastText,
                backgroundColor: "#900078",
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: '#000b10',
                p:2,
                '&:disabled': {
                    backgroundColor: "#9d729c",
                    color: "#333",
                }
            }}
        >
                {isLoading ? <CircularProgress size={24} color="inherit"/> : <SystemUpdateAltIcon/>}
        </Button>
        </Tooltip>
    );
};
