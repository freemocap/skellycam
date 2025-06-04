// skellycam-ui/src/store/thunks/camera-thunks.ts
import {createAsyncThunk} from '@reduxjs/toolkit';
import {setAvailableCameras, setError, setLoading} from "@/store/slices/cameras-slices/camerasSlice";
import {
    CAMERA_DEFAULT_CONSTRAINTS,
    CameraDevice,
    createDefaultCameraConfig
} from "@/store/slices/cameras-slices/camera-types";


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

export const  detectCameraDevices = createAsyncThunk(
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
            const serializableCameras: CameraDevice[] = validatedCameras.map((device, index) => ({
                ...device.toJSON(),
                index: index,
                cameraId: device.deviceId.slice(-5), // Camera ID is the last 5 characters of the device ID
                selected: true,
                status: 'IDLE',
                constraints: CAMERA_DEFAULT_CONSTRAINTS,
                config: createDefaultCameraConfig(index, device.label)
            }));
            console.log(`Detected ${serializableCameras.length} camera(s)`, serializableCameras);
            dispatch(setAvailableCameras(serializableCameras));
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
