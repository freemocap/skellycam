import { z } from "zod";
import {CurrentFrameRateSchema} from "@/types/zod-schemas/SkellyCamAppStateSchema";
import {createSlice} from "@reduxjs/toolkit";

type AppState = {
    isRecording: boolean;
    recordingDirectory?: string;
    framerate: z.infer<typeof CurrentFrameRateSchema> | null;
};

const initialState: AppState = {
    isRecording: false,
    framerate: null
}

export const appStateSlice = createSlice({
    name: 'appState',
    initialState,
    reducers: {
        setIsRecording: (state, action) => {
            state.isRecording = action.payload;
        },
        setRecordingDirectory: (state, action) => {
            state.recordingDirectory = action.payload;
        },
        setFramerate: (state, action) => {
            state.framerate = action.payload;
        }
    }
})
export const { setIsRecording, setRecordingDirectory, setFramerate } = appStateSlice.actions;
export default appStateSlice.reducer;
