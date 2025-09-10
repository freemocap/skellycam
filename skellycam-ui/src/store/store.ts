import {configureStore} from "@reduxjs/toolkit";
import {framerateSlice} from "./slices/framerate/framerate-slice";
import {cameraSlice} from "./slices/cameras/cameras-slice";
import {recordingSlice} from "./slices/recording/recording-slice";
import {serverSlice} from "./slices/server/server-slice";
import {themeSlice} from "./slices/theme/theme-slice";
import {videosSlice} from "./slices/videos/videos-slice";
import {logRecordsSlice} from "./slices/log-records/log-records-slice";
import {connectionMiddleware} from "@/store/middleware/connection-middleware";

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        framerate: framerateSlice.reducer,
        logs: logRecordsSlice.reducer,
        server: serverSlice.reducer,
        theme: themeSlice.reducer,
        videos: videosSlice.reducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                // Ignore these paths for serialization checks (dates, etc)
                ignoredPaths: ['server.lastHealthCheck', 'logs.entries'],
                ignoredActions: ['logs/addLogs'],
            },
        }).concat(connectionMiddleware),
});


