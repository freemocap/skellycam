import { configureStore } from "@reduxjs/toolkit"
import { logsSlice } from "./slices/logs-slice/LogsSlice"
import {latestFrontendPayloadSlice} from "./slices/frontend-payload-slice/latestFrontendPayloadSlice"
import {recordingInfoSlice} from "./slices/recordingInfoSlice"
import {framerateSlice} from "./slices/framerateSlice"
import {camerasSlice} from "@/store/slices/cameras-slice/camerasSlice";

export const AppStateStore = configureStore({
    reducer: {
        cameras: camerasSlice.reducer,
        latestPayload: latestFrontendPayloadSlice.reducer,
        logs: logsSlice.reducer,
        recordingStatus: recordingInfoSlice.reducer,
        framerate: framerateSlice.reducer,
    },
})

export type RootState = ReturnType<typeof AppStateStore.getState>
export type AppDispatch = typeof AppStateStore.dispatch
