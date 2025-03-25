import { PayloadAction, createSlice } from '@reduxjs/toolkit';
import {RootState} from "@/store/AppStateStore";
import {CameraConfig, CameraConfigs} from "@/store/slices/cameras-slices/camera-types";
import { enableMapSet } from 'immer';

// This slice maintains the state of user-selected camera configurations
// that MAY be different from the actual connected camera configurations
interface UserCameraConfigsState {
    // User's desired configurations for cameras
    userConfigs: CameraConfigs | null;
    // Track which configs have pending changes
    pendingChanges:string[];
    // Loading state for applying configurations
    isApplying: boolean;
    // Any error messages from applying configurations
    error: string | null;
}

const initialState: UserCameraConfigsState = {
    userConfigs: null,
    pendingChanges: [],
    isApplying: false,
    error: null,
};

export const userCameraConfigsSlice = createSlice({
    name: 'userCameraConfigs',
    initialState,
    reducers: {
        setUserSelectedCameraConfigs: (
            state,
            action: PayloadAction<{ deviceId: string; config: CameraConfig }>
        ) => {
            const { deviceId, config } = action.payload;
            state.userConfigs = {
                ...state.userConfigs,
                [deviceId]: config,
            };
            // Add to pending changes if not already present
            if (!state.pendingChanges.includes(deviceId)) {
                state.pendingChanges.push(deviceId);
            }
        },
        clearPendingChanges: (state) => {
            state.pendingChanges = [];
        },
        setApplying: (state, action: PayloadAction<boolean>) => {
            state.isApplying = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
        },
    },
});

// Selectors
export const selectUserConfigs = (state: RootState) =>
    state.userCameraConfigs.userConfigs;

export const selectUserCameraConfig = (deviceId: string) =>
    (state: RootState) => state.userCameraConfigs.userConfigs?.[deviceId];


export const selectHasPendingChanges = (deviceId: string) =>
    (state: RootState) => state.userCameraConfigs.pendingChanges.includes(deviceId);

// Action creators
export const {
    setUserSelectedCameraConfigs,
    clearPendingChanges,
    setApplying,
    setError,
} = userCameraConfigsSlice.actions;

export default userCameraConfigsSlice.reducer;
