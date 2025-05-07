import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'

import {z} from 'zod'
import {CurrentFramerateSchema} from "@/store/slices/framerateTrackerSlice";
import {CameraConfigs, CameraConfigsSchema} from "@/store/slices/cameras-slices/camera-types";


export const FrontendFramePayloadSchema = z.object({
    camera_configs: CameraConfigsSchema,
    multi_frame_metadata: z.record(z.string(), z.unknown()),
    utc_ns_to_perf_ns: z.record(z.string(), z.number()),
    multi_frame_number: z.number().int(),
    backend_framerate: CurrentFramerateSchema.nullable(),
    frontend_framerate: CurrentFramerateSchema.nullable(),
});

export type FrontendFramePayload = z.infer<typeof FrontendFramePayloadSchema>;

interface FrontendPayloadState {
    latestFrontendPayload: FrontendFramePayload | null;
}

const initialState: FrontendPayloadState = {
    latestFrontendPayload: null,
}

export const latestFrontendPayloadSlice = createSlice({
    name: 'frontendPayload',
    initialState,
    reducers: {
        setLatestFrontendPayload: (state, action: PayloadAction<z.infer<typeof FrontendFramePayloadSchema>>) => {
            state.latestFrontendPayload = action.payload;
        }
    }
})

export const { setLatestFrontendPayload } = latestFrontendPayloadSlice.actions
export default latestFrontendPayloadSlice.reducer
