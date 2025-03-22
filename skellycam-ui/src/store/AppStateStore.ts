import { configureStore } from "@reduxjs/toolkit"
import { logRecordsSlice } from "./slices/LogRecordsSlice"
import {latestFrontendPayloadSlice} from "./slices/latestFrontendPayloadSlice"
import {recordingInfoSlice} from "./slices/recordingInfoSlice"
import {framerateTrackerSlice} from "./slices/framerateTrackerSlice"
import {cameraDevicesSlice} from "@/store/slices/cameraDevicesSlice";

export const AppStateStore = configureStore({
    reducer: {
        cameraDevices: cameraDevicesSlice.reducer,
        latestPayload: latestFrontendPayloadSlice.reducer,
        logRecords: logRecordsSlice.reducer,
        recordingStatus: recordingInfoSlice.reducer,
        framerateTracker: framerateTrackerSlice.reducer,
    },
})

export type RootState = ReturnType<typeof AppStateStore.getState>
export type AppDispatch = typeof AppStateStore.dispatch
