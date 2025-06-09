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
        setAvailableCameras: (state, action: PayloadAction<CameraDevice[]>) => {
            action.payload.forEach(device => {
                const cameraId = device.cameraId;
                const existingCamera = state.cameras[cameraId];

                state.cameras[cameraId] = {
                    ...device,
                    selected: existingCamera ? existingCamera.selected : device.selected,
                    config: existingCamera?.config || device.config
                };
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

export const selectAllCameras = (state: RootState) => state.cameras.cameras;

export const selectSelectedDevices = createSelector(
    [selectAllCameras],
    (cameras) => {
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
    setAvailableCameras,
    setLoading,
    setCameraStatus,
    toggleCameraSelection,
    updateCameraConfig,
    setError
} = camerasSlice.actions;

export default camerasSlice.reducer;

