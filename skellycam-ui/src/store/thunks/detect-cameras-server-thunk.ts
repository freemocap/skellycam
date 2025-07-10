import {createAsyncThunk} from "@reduxjs/toolkit";
import {
    setError,
    setLoading,
    setAvailableCameras,
    setCameraStatus
} from "@/store/slices/cameras-slices/camerasSlice";
import {
    CAMERA_DEFAULT_CONSTRAINTS,
    CameraDevice,
    createDefaultCameraConfig
} from "@/store/slices/cameras-slices/camera-types";
import { urlService } from "@/services/urlService";
import {RootState} from "@/store/AppStateStore";

export const detectCameraDevices = createAsyncThunk<
    CameraDevice[]
    >('cameras/detectServer',
    async (args, { dispatch, getState }) => {
        const filterVirtual = true;
        dispatch(setLoading(true));

        try {
            const connectUrl = urlService.getCameraUrls().detectCameras;

            console.log(`Detecting cameras at ${connectUrl}`);
            const response = await fetch('${connectUrl}?filter_virtual=${filterVirtual}');

            const data = await response.json();
            const serverCameras = data.cameras;

            // Convert server cameras to CameraDevice objects
            const validatedCameras: CameraDevice[] = [];
            const state = getState() as RootState;
            const existingCameras = state.cameras.cameras;

            Object.keys(existingCameras).forEach(cameraId => {
                const stillExists = serverCameras.some(device => device.index === parseInt(cameraId));
                if (!stillExists) {
                    dispatch(setCameraStatus({ cameraId, status: 'UNAVAILABLE' }));
                }
            });

            for (const serverCamera of serverCameras) {                
                const existingCamera = existingCameras[serverCamera.index];
                const newCamera: CameraDevice = {
                    index: serverCamera.index,
                    deviceId: serverCamera.vendor_id?.toString() + serverCamera.product_id?.toString(),
                    cameraId: serverCamera.index,
                    selected: existingCamera?.selected ?? false,
                    status: 'AVAILABLE', // TODO: do we want to validate the cameras again?
                    label: serverCamera.name,
                    groupId: '', // TODO: not sure if this needs to be passed form the server?
                    kind: 'videoinput',
                    constraints: CAMERA_DEFAULT_CONSTRAINTS,
                    config: existingCamera?.config || 
                    createDefaultCameraConfig(
                        serverCamera.index,
                        serverCamera.name,
                        serverCamera.index
                    )
                };

                validatedCameras.push(newCamera);
            }

            console.log(`After validation, ${validatedCameras.length} camera(s) processed`, validatedCameras);
            dispatch(setAvailableCameras(validatedCameras));
            dispatch(setError(null));
            return validatedCameras;
        } catch (error) {
            // Handle network errors and JSON parsing errors
            const errorMessage = error instanceof Error
                ? `Failed to detect cameras: ${error.message}`
                : 'Failed to detect cameras: Unknown error';

            dispatch(setError(errorMessage));
            console.error(errorMessage, error);
            throw error;
        } finally {
            dispatch(setLoading(false));
        }
    }
);
