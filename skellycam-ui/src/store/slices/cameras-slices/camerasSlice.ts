// skellycam-ui/src/store/slices/camerasSlice.ts
import {createSelector, createSlice, PayloadAction} from '@reduxjs/toolkit'
import {RootState} from "@/store/AppStateStore";
import {
    CameraConfig,
    createDefaultCameraConfig,
    SerializedMediaDeviceInfo
} from "@/store/slices/cameras-slices/camera-types";

export interface CamerasState {
    devices: SerializedMediaDeviceInfo[];
    configs: Record<string, CameraConfig>;
    isLoading: boolean;
    error: string | null;
}

const initialState: CamerasState = {
    devices: [],
    configs: {},
    isLoading: false,
    error: null
}

export const camerasSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        setDetectedDevices: (state, action: PayloadAction<SerializedMediaDeviceInfo[]>) => {
            // Deep clone the devices to ensure all nested properties are properly copied
            state.devices = action.payload.map(device => {
                return JSON.parse(JSON.stringify(device));
            });

            // Initialize config for each device if it doesn't exist
            action.payload.forEach(device => {
                if (!state.configs[device.deviceId]) {
                    state.configs[device.deviceId] = createDefaultCameraConfig(device.index, device.label);
                }
            });
        },
        setLoading: (state, action: PayloadAction<boolean>) => {
            state.isLoading = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
        },
        toggleCameraSelection: (state, action: PayloadAction<string>) => {
            state.devices = state.devices.map(device => {
                if (device.deviceId === action.payload) {
                    const newSelected = !device.selected;

                    // Update the config's 'use_this_camera' property to match selection state
                    if (state.configs[device.deviceId]) {
                        state.configs[device.deviceId].use_this_camera = newSelected;
                    }

                    return { ...device, selected: newSelected };
                }
                return device;
            });
        },
        updateCameraConfig: (state, action: PayloadAction<{
            deviceId: string;
            config: Partial<CameraConfig>;
        }>) => {
            const { deviceId, config } = action.payload;
            if (state.configs[deviceId]) {
                state.configs[deviceId] = {
                    ...state.configs[deviceId],
                    ...config
                };
            }
        },
    },
});

// Selectors
export const selectAllDevices = (state: RootState) => state.cameras.devices;
export const selectSelectedDevices = createSelector(
    [selectAllDevices],
    (devices) => devices.filter(device => device.selected)
);
export const selectCameraConfigs = (state: RootState) => state.cameras.configs;

export const selectConfigsForSelectedDevices = createSelector(
    [selectSelectedDevices, selectCameraConfigs],
    (devices, configs) => {
        const selectedConfigs: Record<string, CameraConfig> = {};
        devices.forEach(device => {
            if (configs[device.deviceId]) {
                selectedConfigs[device.deviceId] = configs[device.deviceId];
            }
        });
        return selectedConfigs;
    }
);

export const {
    setDetectedDevices,
    setLoading,
    toggleCameraSelection,
    updateCameraConfig,
    setError
} = camerasSlice.actions;

export default camerasSlice.reducer;
