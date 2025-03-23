import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import { z } from 'zod';
import {RootState} from "@/store/AppStateStore";

export interface SerializedMediaDeviceInfo {
    index: number;
    deviceId: string;
    groupId: string;
    kind: string;
    label: string;
    selected: boolean;
}

export const CameraConfigSchema = z.object({
    camera_id: z.number(),
    camera_name: z.string(),
    use_this_camera: z.boolean(), // checkbox
    resolution: z.object({ //dropdown of available resolutions, or custom resolution
        width: z.number().int(),
        height: z.number().int()
    }),
    color_channels: z.number(),
    pixel_format: z.string(),
    exposure_mode: z.string(), // dropdown of available exposure modes, Manual, Auto, Recommended
    exposure: z.union([z.number(), z.string()]), // either AUTO or a number between -12 and -5
    framerate: z.number(), // dropdown of available framerates
    rotation: z.string(), // dropdown of available rotation options, 0, 90, 180, 270
    capture_fourcc: z.string(), // dropdown of available capture fourcc options
    writer_fourcc: z.string(), // dropdown of available writer fourcc options
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

export const cameraDevicesSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        setConnectedCameras: (state, action: PayloadAction<CameraConfigs>) => {
            state.connected_cameras = action.payload
        },
        setUserSelectedCameraConfigs: (state, action: PayloadAction<CameraConfigs>) => {
            state.user_selected_camera_configs = action.payload
        },
        setBrowserDetectedDevices: (state, action: PayloadAction<SerializedMediaDeviceInfo[]>) => {
            state.browser_detected_devices = action.payload;
        },
        setLoading: (state, action: PayloadAction<boolean>) => {
            state.isLoading = action.payload;
        },
        setError: (state, action: PayloadAction<string | null>) => {
            state.error = action.payload;
        },
        toggleCameraSelection: (state, action: PayloadAction<string>) => {
            state.browser_detected_devices = state.browser_detected_devices.map( device =>
                device.deviceId === action.payload
                    ? { ...device, selected: !device.selected }
                    : device

            )
        },
    },
})
export const selectSelectedCameras = (state: RootState) =>
    state.cameraDevices.browser_detected_devices.filter(device => device.selected);

export const {
    setConnectedCameras,
    setUserSelectedCameraConfigs,
    setBrowserDetectedDevices,
    setLoading,
    toggleCameraSelection,
    setError
} = cameraDevicesSlice.actions

export default cameraDevicesSlice.reducer
