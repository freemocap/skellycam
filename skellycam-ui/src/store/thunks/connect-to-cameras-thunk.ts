import {createAsyncThunk} from "@reduxjs/toolkit";
import {CameraConfigs} from "@/store/slices/cameras-slices/camera-types";
import {setError, setLoading} from "@/store/slices/cameras-slices/detectedCamerasSlice";

interface ConnectCamerasPayload {
    camera_configs: CameraConfigs;
}

export const connectToCameras = createAsyncThunk(
    'cameras/connect',
    async (cameraConfigs: CameraConfigs, {dispatch}) => {
        if (!cameraConfigs || Object.keys(cameraConfigs).length === 0) {
            throw new Error('No camera devices provided for connection');
        }
        dispatch(setLoading(true));
        const connectUrl = 'http://localhost:8006/skellycam/cameras/connect'

        const payload: ConnectCamerasPayload = {
            camera_configs: cameraConfigs
        };

        const requestBody = JSON.stringify(payload, null, 2);
        try {
            console.log(`Connecting to cameras at ${connectUrl} with body:`, requestBody);
            const response = await fetch(connectUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: requestBody
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            dispatch(setError(null));
        } catch (error) {
            const errorMessage = 'Failed to connect to cameras';
            dispatch(setError(errorMessage));
            console.error(errorMessage, error);
            throw error;
        } finally {
            dispatch(setLoading(false));
        }
    }
);
