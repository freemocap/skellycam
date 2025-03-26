// ConnectToCamerasButton.tsx
import React from 'react';
import {Button, darken, lighten} from '@mui/material';
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {selectSelectedCameras} from "@/store/slices/cameras-slices/detectedCamerasSlice";
import {useAppDispatch, useAppSelector} from "@/store/AppStateStore";
import {connectToCameras} from "@/store/thunks/connect-to-cameras-thunk";
import {selectUserConfigs} from "@/store/slices/cameras-slices/userCameraConfigs";

export const ConnectToCamerasButton = () => {
    const dispatch = useAppDispatch();
    const isLoading = useAppSelector(state => state.detectedCameras.isLoading);
    const selectedCameras = useAppSelector(selectSelectedCameras);
    const userConfigs = useAppSelector(selectUserConfigs);
    const handleConnectAndDetect = async () => {
        if (isLoading ) {
            console.log('Camera connection is already in progress ');
            return;
        }


        try {
            if (selectedCameras && selectedCameras.length > 0) {
                // Create a record of camera configs for selected cameras only
                const selectedConfigs = selectedCameras.reduce((acc, camera) => {
                    const config = userConfigs[camera.deviceId];
                    if (config) {
                        acc[camera.index] = config;
                    }
                    return acc;
                }, {} as Record<number, any>);

                if (Object.keys(selectedConfigs).length > 0) {
                    await dispatch(connectToCameras(selectedConfigs)).unwrap();
                    console.log('Connected to selected cameras with configs:', selectedConfigs);
                }
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
            disabled={!selectedCameras || selectedCameras.length === 0}
            sx={{
                m: 1,
                p: 2,
                fontSize: 'small',
                color: extendedPaperbaseTheme.palette.primary.contrastText,
                backgroundColor: "#900078",
                border: `2px solid ${extendedPaperbaseTheme.palette.primary.light}`,
                '&:disabled': {
                    backgroundColor:"#9d729c",
                    color: "#333",
                }
            }}
        >
            Connect/Apply
        </Button>
    );
};
