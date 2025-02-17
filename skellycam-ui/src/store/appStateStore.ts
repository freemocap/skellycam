import { configureStore } from '@reduxjs/toolkit'
import counterReducer from './slices/counterSlice'
import {availableCamerasSlice} from "@/store/slices/availableCamerasSlice";

export const AppStateStore = configureStore({
    reducer: {
        counter: counterReducer,
        availableCameras: availableCamerasSlice.reducer,
    },
})

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof AppStateStore.getState>
// Inferred type: {posts: PostsState, comments: CommentsState, users: UsersState}
export type AppDispatch = typeof AppStateStore.dispatch
