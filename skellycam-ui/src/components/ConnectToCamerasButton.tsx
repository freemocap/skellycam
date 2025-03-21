import React from 'react';
import {Button} from '@mui/material';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {useAppDispatch, useAppSelector} from "@/store/hooks";
import {connectToCameras, detectBrowserDevices} from "@/store/thunks/camera-thunks";

export const ConnectToCamerasButton = () => {
    const dispatch = useAppDispatch();
    const isLoading = useAppSelector(state => state.cameras.isLoading);
    const detectedCameras = useAppSelector(state => state.cameras.browser_detected_devices);

    const handleConnectAndDetect = async () => {
        if (isLoading) {
            console.log('Camera connection is already in progress.');
            return;
        }

        try {

            if (detectedCameras && detectedCameras.length > 0) {
                await dispatch(connectToCameras(detectedCameras)).unwrap();
                console.log('Camera detection and connection completed successfully');
            } else {
                console.log('No cameras detected to connect to');
            }
        } catch (error) {
            console.error('Error during camera detection and connection:', error);
        }
    };

    return (
        <Button
            variant="contained"
            onClick={handleConnectAndDetect}
            sx={{
                m: 2,
                p: 2,
                fontSize: '1.25rem',
                color: extendedPaperbaseTheme.palette.primary.contrastText,
                backgroundColor: "#900078",
                border: `2px solid ${extendedPaperbaseTheme.palette.primary.main}`,
            }}
        >
            Detect/Connect to Cameras
        </Button>
    );
};
