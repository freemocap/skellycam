import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import { RootState } from '../../AppStateStore';
import {CameraConfigs} from "@/store/slices/cameras-slices/camera-types";

// This slice maintains the state of cameras that are ACTUALLY connected
// and their current/extracted configurations as reported by the backend
interface ConnectedCamerasState {
    // Configurations of currently connected cameras as reported by backend
    connectedConfigs: CameraConfigs | null;
    // Loading state for camera operations
    isLoading: boolean;
    // Any error messages from camera operations
    error: string | null;
    // Timestamp of last update from backend
    lastUpdateTime: number | null;
}

const initialState: ConnectedCamerasState = {
    connectedConfigs: null,
    isLoading: false,
    error: null,
    lastUpdateTime: null,
};

export const connectedCamerasSlice = createSlice({
    name: 'connectedCameras',
    initialState,
    reducers: {
        // Update the current state of connected cameras
        setConnectedCameraConfigs: (state, action: PayloadAction<CameraConfigs>) => {
            state.connectedConfigs = action.payload;
            state.lastUpdateTime = Date.now();
        },
        setLoading: (state, action: PayloadAction<boolean>) => {
            state.isLoading = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
        },
    },
});

// Selectors
export const selectConnectedConfigs = (state: RootState) =>
    state.connectedCameras.connectedConfigs;

export const selectConnectedCameraConfig = (deviceId: string) =>
    (state: RootState) => state.connectedCameras.connectedConfigs?.[deviceId];

// Action creators
export const {
    setConnectedCameraConfigs,
    setLoading,
    setError,
} = connectedCamerasSlice.actions;

export default connectedCamerasSlice.reducer;
