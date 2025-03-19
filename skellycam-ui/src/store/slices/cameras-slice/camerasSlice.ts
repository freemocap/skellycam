import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {z} from 'zod';
import {CameraConfigs, DetectedCameras} from "@/store/slices/cameras-slice/camera-types";

export interface DetectedDevicesState {
    detected_cameras: DetectedCameras | null;
    connected_cameras:  CameraConfigs | null;
    user_selected_camera_configs: CameraConfigs | null;
}

const initialState: DetectedDevicesState = {
    detected_cameras: null,
    connected_cameras: null,
    user_selected_camera_configs: null,
}

export const detectedDevicesSlice = createSlice({
    name: 'detectedDevices',
    initialState,
    reducers: {
        setDetectedDevices: (state, action: PayloadAction< DetectedCameras >) => {
            state.detected_cameras = action.payload
        },
        setConnectedCameras: (state, action: PayloadAction< CameraConfigs>) => {
            state.connected_cameras = action.payload
        },
        setUserSelectedCameraConfigs: (state, action: PayloadAction<CameraConfigs>) => {
            state.user_selected_camera_configs = action.payload
        },
    },
})

// Action creators are generated for each case reducer function
export const { setDetectedDevices , setConnectedCameras, setUserSelectedCameraConfigs } = detectedDevicesSlice.actions

export default detectedDevicesSlice.reducer
