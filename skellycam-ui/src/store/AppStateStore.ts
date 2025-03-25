import {configureStore} from "@reduxjs/toolkit"
import {latestFrontendPayloadSlice} from "./slices/latestFrontendPayloadSlice"
import {recordingInfoSlice} from "./slices/recordingInfoSlice"
import {framerateTrackerSlice} from "./slices/framerateTrackerSlice"
import {detectedCamerasSlice} from "@/store/slices/cameras-slices/detectedCamerasSlice";
import {connectedCamerasSlice} from "@/store/slices/cameras-slices/connectedCameraConfigsSlice";
import {userCameraConfigsSlice} from "@/store/slices/cameras-slices/userCameraConfigs";
import {logRecordsSlice} from "@/store/slices/logRecordsSlice";
import {type TypedUseSelectorHook, useDispatch, useSelector} from "react-redux";

export const AppStateStore = configureStore({
    reducer: {
        detectedCameras: detectedCamerasSlice.reducer,
        connectedCameras: connectedCamerasSlice.reducer,
        userCameraConfigs: userCameraConfigsSlice.reducer,
        latestPayload: latestFrontendPayloadSlice.reducer,
        logRecords: logRecordsSlice.reducer,
        recordingStatus: recordingInfoSlice.reducer,
        framerateTracker: framerateTrackerSlice.reducer,
    },
})

export type RootState = ReturnType<typeof AppStateStore.getState>
export type AppDispatch = typeof AppStateStore.dispatch
export const useAppDispatch = () => useDispatch<AppDispatch>()
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector