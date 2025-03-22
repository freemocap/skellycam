// ConnectToCamerasButton.tsx
import React from 'react';
import {Button, darken, lighten} from '@mui/material';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {connectToCameras} from "@/store/thunks/camera-thunks";
import {selectSelectedCameras} from "@/store/slices/cameraDevicesSlice";

export const ConnectToCamerasButton = () => {
    const dispatch = useAppDispatch();
    const isLoading = useAppSelector(state => state.cameraDevices.isLoading);
    const selectedCameras = useAppSelector(selectSelectedCameras);

    const handleConnectAndDetect = async () => {
        if (isLoading) {
            console.log('Camera connection is already in progress.');
            return;
        }

        try {
            if (selectedCameras && selectedCameras.length > 0) {
                // Pass only the selected cameras to the thunk
                await dispatch(connectToCameras(selectedCameras)).unwrap();
                console.log('Connected to selected cameras:', selectedCameras);
            } else {
                console.log('No cameras selected to connect to');
            }
        } catch (error) {
            console.error('Error connecting to cameras:', error);
        }
    };

    return (
        <Button
            variant="contained"
            onClick={handleConnectAndDetect}
            disabled={!selectedCameras || selectedCameras.length === 0} // Disable if no cameras selected
            sx={{
                m: 2,
                p: 2,
                fontSize: '1.25rem',
                color: extendedPaperbaseTheme.palette.primary.contrastText,
                backgroundColor: "#900078",
                border: `2px solid ${extendedPaperbaseTheme.palette.primary.main}`,
                '&:disabled': {
                    backgroundColor:"#9d729c",
                    color: "#333",
                }
            }}
        >
            Connect to Selected Cameras
        </Button>
    );
};
