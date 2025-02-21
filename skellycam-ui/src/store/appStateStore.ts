import {configureStore} from '@reduxjs/toolkit'
import counterReducer from './slices/counterSlice'
import {availableCamerasSlice} from "@/store/slices/availableCamerasSlice";
import {appStateSlice} from './slices/appState';
// import {cameraConfigsSlice} from "@/store/slices/cameraConfigsSlice";

export const AppStateStore = configureStore({
    reducer: {
        counter: counterReducer, // demo/example
        availableCameras: availableCamerasSlice.reducer,
        appState: appStateSlice.reducer,
        // cameraConfigs: cameraConfigsSlice.reducer,
    },
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                ignoredActions: ['websocket/message'], // Ignore the websocket/message action bc it contains a binary payloads
            },
        }),

})

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof AppStateStore.getState>
// Inferred type: {posts: PostsState, comments: CommentsState, users: UsersState}
export type AppDispatch = typeof AppStateStore.dispatch
