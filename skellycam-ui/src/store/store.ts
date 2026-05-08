import {configureStore} from "@reduxjs/toolkit";
import {cameraSlice} from "./slices/cameras/cameras-slice";
import {recordingSlice} from "./slices/recording/recording-slice";
import {themeSlice} from "./slices/theme/theme-slice";
import {videosSlice} from "./slices/videos/videos-slice";
import {settingsSlice} from "./slices/settings/settings-slice";

// ── Redux DevTools (remote, dev mode only) ─────────────────────
// Tauri can't sideload the Redux DevTools browser extension. Instead we
// use @redux-devtools/remote to stream actions/state over a WebSocket to
// the standalone Redux DevTools app. Run this in a separate terminal:
//   npx @redux-devtools/cli --open
//
// In production builds, Vite tree-shakes the entire block since
// import.meta.env.DEV is statically replaced with false.
import { composeWithDevTools } from '@redux-devtools/remote';

export const store = configureStore({
    reducer: {
        cameras: cameraSlice.reducer,
        recording: recordingSlice.reducer,
        theme: themeSlice.reducer,
        videos: videosSlice.reducer,
        settings: settingsSlice.reducer,
    },
    devTools: false,
    enhancers: (getDefaultEnhancers) => {
        if (import.meta.env.DEV) {
            const devCompose = composeWithDevTools({ realtime: true, port: 8000 });
            // Apply default enhancers (thunk middleware etc.) through
            // composeWithDevTools so the DevTools can instrument them.
            const composedEnhancer = devCompose(...getDefaultEnhancers());
            return [composedEnhancer] as any;
        }
        return getDefaultEnhancers();
    },
});
