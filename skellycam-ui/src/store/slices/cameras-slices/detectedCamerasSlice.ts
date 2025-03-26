import {createSelector, PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {RootState} from "@/store/AppStateStore";
import {SerializedMediaDeviceInfo} from "@/store/slices/cameras-slices/camera-types";


export interface DetectedCamerasState {
    browserDetectedCameras: SerializedMediaDeviceInfo[];
    isLoading: boolean;
    error: string | null;
}

const initialState: DetectedCamerasState = {
    browserDetectedCameras: [],
    isLoading: false,
    error: null
}

export const detectedCamerasSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        setBrowserDetectedDevices: (state, action: PayloadAction<SerializedMediaDeviceInfo[]>) => {
            state.browserDetectedCameras = action.payload;
        },
        setLoading: (state, action: PayloadAction<boolean>) => {
            state.isLoading = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
        },
        toggleCameraSelection: (state, action: PayloadAction<string>) => {
            state.browserDetectedCameras = state.browserDetectedCameras.map(device =>
                device.deviceId === action.payload
                    ? { ...device, selected: !device.selected }
                    : device
            );
        },
    },
});
const selectDetectedCameras = (state: RootState) => state.detectedCameras.browserDetectedCameras;

export const selectSelectedCameras = createSelector(
    [selectDetectedCameras],
    (cameras) => cameras.filter(device => device.selected)
);
export const {
    setBrowserDetectedDevices,
    setLoading,
    toggleCameraSelection,
    setError
} = detectedCamerasSlice.actions;
