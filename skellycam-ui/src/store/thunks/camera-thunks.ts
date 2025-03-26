// skellycam-ui/src/store/thunks/camera-thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import {
    selectConfigsForSelectedDevices,
    setDetectedDevices, setError,
    setLoading
} from "@/store/slices/cameras-slices/camerasSlice";
import {CAMERA_DEFAULT_CONSTRAINTS} from "@/store/slices/cameras-slices/camera-types";


const isVirtualCamera = (label: string): boolean => {
    const virtualCameraKeywords = ['virtual'];
    return virtualCameraKeywords.some(keyword => label.toLowerCase().includes(keyword));
};
export const validateVideoStream = async (deviceId: string): Promise<boolean> => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                deviceId: { exact: deviceId }
            }
        });

        // Create a video element to test the stream
        const video = document.createElement('video');
        video.srcObject = stream;
        return new Promise((resolve) => {
            video.onloadedmetadata = () => {
                // Check if the video has valid dimensions
                if (video.videoWidth > 0 && video.videoHeight > 0) {
                    resolve(true);
                } else {
                    resolve(false);
                }

                // Cleanup
                stream.getTracks().forEach(track => track.stop());
                video.remove();
            };

            // Handle failures
            video.onerror = () => {
                stream.getTracks().forEach(track => track.stop());
                video.remove();
                resolve(false);
            };

            // Set timeout for devices that might hang
            setTimeout(() => {
                stream.getTracks().forEach(track => track.stop());
                video.remove();
                resolve(false);
            }, 3000);
        });
    } catch (error) {
        console.warn(`Failed to validate device ${deviceId}:`, error);
        return false;
    }
};

export const detectBrowserDevices = createAsyncThunk(
    'cameras/detectBrowserDevices',
    async (filterVirtual: boolean = true, { dispatch }) => {
        try {
            dispatch(setLoading(true));
            const devices = await navigator.mediaDevices.enumerateDevices();
            // Get the video input devices (cameras)
            const cameras = devices.filter(({ kind }) => kind === "videoinput");
            if (cameras.length === 0) {
                dispatch(setError('No camera devices found'));
                console.warn('No camera devices found');
                return [];
            }
            console.log(`Found ${cameras.length} camera(s) `, cameras);

            // First filter out virtual cameras if requested
            const initialFiltered = filterVirtual ?
                cameras.filter(({ label }) => !isVirtualCamera(label)) :
                cameras;
            console.log(`After removing virtual cameras, ${initialFiltered.length} camera(s) remain`, initialFiltered);

            // Now validate each camera
            const validatedCameras = [];
            for (const camera of initialFiltered) {
                const isValid = await validateVideoStream(camera.deviceId);
                if (isValid) {
                    validatedCameras.push(camera);
                } else {
                    console.warn(`Camera ${camera.label} failed validation - skipping`);
                }
            }
            console.log(`After validation, ${validatedCameras.length} camera(s) remain`, validatedCameras);

            // Convert MediaDeviceInfo objects to plain serializable objects and add index
            const serializableCameras = validatedCameras.map((device, index) => ({
                ...device.toJSON(),
                index: index,
                selected: true,
                constraints: CAMERA_DEFAULT_CONSTRAINTS
            }));
            console.log(`Detected ${serializableCameras.length} camera(s)`, serializableCameras);

            dispatch(setDetectedDevices(serializableCameras));
            dispatch(setError(null));
            return serializableCameras;
        } catch (error) {
            dispatch(setError('Failed to detect browser devices'));
            console.error('Error detecting browser devices:', error);
        } finally {
            dispatch(setLoading(false));
        }
    }
);
export const connectToCameras = createAsyncThunk(
    'cameras/connect',
    async (_, { dispatch, getState }) => {
        const state = getState() as any;
        const cameraConfigs = selectConfigsForSelectedDevices(state);

        if (!cameraConfigs || Object.keys(cameraConfigs).length === 0) {
            const errorMsg = 'No camera devices selected for connection';
            dispatch(setError(errorMsg));
            throw new Error(errorMsg);
        }

        dispatch(setLoading(true));
        const connectUrl = 'http://localhost:8006/skellycam/cameras/connect';

        const payload = {
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

            // Parse the response body
            const data = await response.json();

            // Check for different error status codes
            if (!response.ok) {
                let errorMsg = 'Failed to connect to cameras';

                // Handle FastAPI validation errors (422 Unprocessable Entity)
                if (response.status === 422 && data.detail) {
                    // Format validation errors from FastAPI
                    if (Array.isArray(data.detail)) {
                        const validationErrors = data.detail.map((err: any) => {
                            // Extract location and specific error
                            const location = err.loc.slice(1).join(' > ');
                            return `${location}: ${err.msg}`;
                        }).join('\n');

                        errorMsg = `Validation errors:\n${validationErrors}`;
                    } else {
                        errorMsg = `Validation error: ${JSON.stringify(data.detail)}`;
                    }
                    console.error('Validation errors:', data.detail);
                } else if (data.error) {
                    // Handle custom error messages
                    errorMsg = data.error;
                } else {
                    errorMsg = `HTTP error! status: ${response.status}`;
                }

                dispatch(setError(errorMsg));
                throw new Error(errorMsg);
            }

            dispatch(setError(null));
            return data;
        } catch (error) {
            // Handle network errors and JSON parsing errors
            const errorMessage = error instanceof Error
                ? `Failed to connect to cameras: ${error.message}`
                : 'Failed to connect to cameras: Unknown error';

            dispatch(setError(errorMessage));
            console.error(errorMessage, error);
            throw error;
        } finally {
            dispatch(setLoading(false));
        }
    }
);