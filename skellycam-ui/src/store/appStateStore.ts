import { configureStore } from "@reduxjs/toolkit"
import { logsSlice } from "./slices/LogsSlice"
import { detectedDevicesSlice } from "@/store/slices/cameras-slice/camerasSlice"
import {latestFrontendPayloadSlice} from "./slices/latestFrontendPayloadSlice"
import {recordingInfoSlice} from "./slices/recordingInfoSlice"
import {framerateSlice} from "./slices/framerateSlice"

export const AppStateStore = configureStore({
    reducer: {
        detectedDevices: detectedDevicesSlice.reducer,
        frontendPayload: latestFrontendPayloadSlice.reducer,
        logs: logsSlice.reducer,
        recordingStatus: recordingInfoSlice.reducer,
        framerate: framerateSlice.reducer,
    },
})

export type RootState = ReturnType<typeof AppStateStore.getState>
export type AppDispatch = typeof AppStateStore.dispatch
