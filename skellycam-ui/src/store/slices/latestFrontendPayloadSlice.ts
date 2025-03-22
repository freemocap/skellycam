import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'

import {z} from 'zod'
import {CameraConfigs, CameraConfigsSchema} from "@/store/slices/cameraDevicesSlice";
import {CurrentFramerateSchema} from "@/store/slices/framerateTrackerSlice";
export const JpegImagesSchema = z.record(
    z.string(),
    z.string()
);

export const FrontendFramePayloadSchema = z.object({
    jpeg_images: JpegImagesSchema,
    camera_configs: CameraConfigsSchema,
    multi_frame_metadata: z.record(z.string(), z.unknown()),
    utc_ns_to_perf_ns: z.record(z.string(), z.number()),
    multi_frame_number: z.number().int(),
    backend_framerate: CurrentFramerateSchema.nullable(),
    frontend_framerate: CurrentFramerateSchema.nullable(),
});

export type JpegImages = z.infer<typeof JpegImagesSchema>;
export type FrontendFramePayload = z.infer<typeof FrontendFramePayloadSchema>;

interface FrontendPayloadState {
    latestFrontendPayload: FrontendFramePayload | null;
    latestImages: JpegImages | null;
    cameraConfigs: CameraConfigs | null;
}

const initialState: FrontendPayloadState = {
    latestFrontendPayload: null,
    latestImages: null,
    cameraConfigs: null
}

export const latestFrontendPayloadSlice = createSlice({
    name: 'frontendPayload',
    initialState,
    reducers: {
        setLatestFrontendPayload: (state, action: PayloadAction<z.infer<typeof FrontendFramePayloadSchema>>) => {
            state.latestFrontendPayload = action.payload;
            state.latestImages = action.payload.jpeg_images as JpegImages;

            if (action.payload.camera_configs) {
                state.cameraConfigs = action.payload.camera_configs as CameraConfigs;
            }
        }
    }
})

export const { setLatestFrontendPayload } = latestFrontendPayloadSlice.actions
export default latestFrontendPayloadSlice.reducer
