// skellycam-ui/src/store/slices/cameras-slices/camerasSlice.ts
import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit'
import {RootState} from "@/store/AppStateStore";
import {CameraConfig, CameraDevice, createDefaultCameraConfig} from "@/store/slices/cameras-slices/camera-types";

export interface CamerasState {
    cameras: Record<string, CameraDevice>;
    isLoading: boolean;
    error: string | null;
}

const initialState: CamerasState = {
    cameras: {},
    isLoading: false,
    error: null
}

export const camerasSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        setDetectedDevices: (state, action: PayloadAction<CameraDevice[]>) => {
            // Create a new Record of cameras
            const newCameras: Record<string, CameraDevice> = {};

            // Process each device
            action.payload.forEach(device => {
                const cameraId = device.cameraId;

                // If the camera already exists, preserve its config and selected state
                const existingCamera = state.cameras[cameraId];

                // Instead of direct assignment, add each camera individually
                state.cameras[cameraId] = {
                    ...device,
                    // Preserve the existing selection state or default to false
                    selected: existingCamera ? existingCamera.selected : true,
                    // Preserve the existing config or create a new default one
                    config: existingCamera?.config || createDefaultCameraConfig(device.index, device.label)
                };
            });

            // Remove cameras that are no longer present
            Object.keys(state.cameras).forEach(id => {
                if (!action.payload.some(device => device.cameraId === id)) {
                    delete state.cameras[id];
                }
            });
        },
        setLoading: (state, action: PayloadAction<boolean>) => {
            state.isLoading = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
        },
        setCameraStatus: (state, action: PayloadAction<{cameraId: string, status: string}>) => {
            const { cameraId, status } = action.payload;
            if (state.cameras[cameraId]) {
                state.cameras[cameraId].status = status;
            }
        },
        toggleCameraSelection: (state, action: PayloadAction<string>) => {
            const cameraId = action.payload;
            if (state.cameras[cameraId]) {
                const newSelected = !state.cameras[cameraId].selected;

                // Update both selected status and config
                state.cameras[cameraId] = {
                    ...state.cameras[cameraId],
                    selected: newSelected,
                    config: {
                        ...state.cameras[cameraId].config,
                        use_this_camera: newSelected
                    }
                };
            }
        },
        updateCameraConfig: (state, action: PayloadAction<{
            cameraId: string;
            config: Partial<CameraConfig>;
        }>) => {
            const { cameraId, config } = action.payload;
            if (state.cameras[cameraId]) {
                state.cameras[cameraId] = {
                    ...state.cameras[cameraId],
                    config: {
                        ...state.cameras[cameraId].config,
                        ...config
                    }
                };
            }
        },
    },
});

// Selectors
export const selectAllCameras = (state: RootState) => state.cameras.cameras;

export const selectSelectedDevices = createSelector(
    [selectAllCameras],
    (cameras) => {
        // Convert Record to array of selected cameras
        return Object.values(cameras).filter(camera => camera.selected);
    }
);

export const selectCameraById = (cameraId: string) =>
    (state: RootState) => state.cameras.cameras[cameraId];

export const selectConfigsForSelectedCameras = createSelector(
    [selectSelectedDevices],
    (selectedCameras) => {
        const selectedConfigs: Record<string, CameraConfig> = {};
        selectedCameras.forEach(camera => {
            if (camera.config) {
                selectedConfigs[camera.cameraId] = camera.config;
            }
        });
        return selectedConfigs;
    }
);

export const {
    setDetectedDevices,
    setLoading,
    setCameraStatus,
    toggleCameraSelection,
    updateCameraConfig,
    setError
} = camerasSlice.actions;

export default camerasSlice.reducer;
