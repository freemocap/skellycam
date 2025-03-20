import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import { z } from 'zod';

export interface SerializedMediaDeviceInfo {
    deviceId: string;
    groupId: string;
    kind: string;
    label: string;
}

export const CameraConfigSchema = z.object({
    camera_id: z.number(),
    camera_name: z.string(),
    use_this_camera: z.boolean(),
    resolution: z.object({
        width: z.number(),
        height: z.number(),
    }),
    color_channels: z.number(),
    pixel_format: z.string(),
    exposure_mode: z.string(),
    exposure: z.union([z.number(), z.string()]),
    framerate: z.number(),
    rotation: z.string(),
    capture_fourcc: z.string(),
    writer_fourcc: z.string(),
});

export const CameraConfigsSchema = z.record(z.string(), CameraConfigSchema );


// Export the types
export type CameraConfig = z.infer<typeof CameraConfigSchema>;
export type CameraConfigs = z.infer<typeof CameraConfigsSchema>;

export interface CamerasState {
    browser_detected_devices: SerializedMediaDeviceInfo[];
    connected_cameras:  CameraConfigs | null;
    user_selected_camera_configs: CameraConfigs | null;
    isLoading: boolean;
    error: string | null;
}

const initialState: CamerasState = {
    connected_cameras: null,
    user_selected_camera_configs: null,
    browser_detected_devices: [],
    isLoading: false,
    error: null
}

export const camerasSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        setConnectedCameras: (state, action: PayloadAction<CameraConfigs>) => {
            state.connected_cameras = action.payload
        },
        setUserSelectedCameraConfigs: (state, action: PayloadAction<CameraConfigs>) => {
            state.user_selected_camera_configs = action.payload
        },
        setBrowserDetectedDevices: (state, action: PayloadAction<MediaDeviceInfo[]>) => {
            state.browser_detected_devices = action.payload;
        },
        setLoading: (state, action: PayloadAction<boolean>) => {
            state.isLoading = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
        },
    },
})

export const {
    setConnectedCameras,
    setUserSelectedCameraConfigs,
    setBrowserDetectedDevices,
    setLoading,
    setError
} = camerasSlice.actions

export default camerasSlice.reducer
