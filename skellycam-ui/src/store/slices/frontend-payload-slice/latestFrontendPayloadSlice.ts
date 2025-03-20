import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {
    FrontendFramePayload,
    FrontendFramePayloadSchema,
    JpegImages
} from "@/store/slices/frontend-payload-slice/FrontendFramePayloadSchema"
import {z} from 'zod'
import {CameraConfigs} from "@/store/slices/cameras-slice/camerasSlice";

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
