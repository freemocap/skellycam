import type { PayloadAction } from '@reduxjs/toolkit'
import { createSlice } from '@reduxjs/toolkit'
import { z } from 'zod'

export const CurrentFramerateSchema = z.object({
    mean_frame_duration_ms: z.number().nullable(),
    mean_frames_per_second: z.number().nullable(),
    calculation_window_size: z.number(),
    framerate_source: z.string(),
});

export type CurrentFramerate = z.infer<typeof CurrentFramerateSchema>;
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
        setFrontendFramerate: (state, action: PayloadAction<CurrentFramerate>) => {
            state.currentFrontendFramerate = CurrentFramerateSchema.parse(action.payload);
            state.loggedFrontendFramerate.push(action.payload);
        },
        setBackendFramerate: (state, action: PayloadAction<CurrentFramerate>) => {
            state.currentBackendFramerate = CurrentFramerateSchema.parse(action.payload);
            state.loggedBackendFramerate.push(action.payload);
        },
    }
})

export const { setFrontendFramerate,setBackendFramerate } = framerateSlice.actions
export default framerateSlice.reducer
