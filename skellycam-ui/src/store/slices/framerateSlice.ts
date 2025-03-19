import type { PayloadAction } from '@reduxjs/toolkit'
import { createSlice } from '@reduxjs/toolkit'
import { z } from 'zod'

export const CurrentFramerateSchema = z.object({
    mean_frame_duration_ms: z.number(),
    mean_frames_per_second: z.number(),
    recent_frames_per_second: z.number(),
    recent_mean_frame_duration_ms: z.number(),
});

interface FramerateState {
    currentFrontendFramerate: z.infer<typeof CurrentFramerateSchema> | null;
    currentBackendFramerate: z.infer<typeof CurrentFramerateSchema> | null;
    loggedFrontendFramerate: z.infer<typeof CurrentFramerateSchema>[];
    loggedBackendFramerate: z.infer<typeof CurrentFramerateSchema>[];
}

const initialState: FramerateState = {
    currentFrontendFramerate: null,
    currentBackendFramerate: null,
    loggedFrontendFramerate: [],
    loggedBackendFramerate: []
}

export const framerateSlice = createSlice({
    name: 'framerate',
    initialState,
    reducers: {
        setFrontendFramerate: (state, action: PayloadAction<z.infer<typeof CurrentFramerateSchema>>) => {
            state.currentFrontendFramerate = CurrentFramerateSchema.parse(action.payload);
            state.loggedFrontendFramerate.push(action.payload);
        },
        setBackendFramerate: (state, action: PayloadAction<z.infer<typeof CurrentFramerateSchema>>) => {
            state.currentBackendFramerate = CurrentFramerateSchema.parse(action.payload);
            state.loggedBackendFramerate.push(action.payload);
        },
    }
})

export const { setFrontendFramerate,setBackendFramerate } = framerateSlice.actions
export default framerateSlice.reducer
