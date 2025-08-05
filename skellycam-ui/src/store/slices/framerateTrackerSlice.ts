import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {z} from 'zod'
import {FramerateData, FramerateUpdate} from "@/contexts/grpc-context/grpc_generated/skellycam";

export const FramerateHistorgramSchema = z.object({
    bin_edges: z.array(z.number()),
    bin_counts: z.array(z.number()),
    bin_densities: z.array(z.number()),
})
export const CurrentFramerateSchema = z.object({
    mean_frame_duration_ms: z.number(),
    mean_frames_per_second: z.number(),
    frame_duration_max: z.number(),
    frame_duration_min: z.number(),
    frame_duration_mean: z.number(),
    frame_duration_stddev: z.number(),
    frame_duration_median: z.number(),
    frame_duration_coefficient_of_variation: z.number(),
    calculation_window_size: z.number(),
    framerate_source: z.string(),
});
export type CurrentFramerate = z.infer<typeof CurrentFramerateSchema>;
// Helper function to map from gRPC FramerateData to our CurrentFramerate format
const mapFramerateDataToCurrentFramerate = (data: FramerateData): CurrentFramerate => ({
    mean_frame_duration_ms: data.meanFrameDurationMs,
    mean_frames_per_second: data.meanFramesPerSecond,
    frame_duration_min: data.frameDurationMin,
    frame_duration_max: data.frameDurationMax,
    frame_duration_mean: data.meanFrameDurationMs,
    frame_duration_stddev: data.frameDurationStddev,
    frame_duration_median: data.frameDurationMedian,
    frame_duration_coefficient_of_variation: data.frameDurationCoefficientOfVariation,
    calculation_window_size: data.calculationWindowSize,
    framerate_source: data.framerateSource
});


// Set a maximum number of framerate entries to store
const MAX_FRAMERATE_ENTRIES = 1000;

interface FramerateState {
    currentFrontendFramerate: z.infer<typeof CurrentFramerateSchema> | null;
    currentBackendFramerate: z.infer<typeof CurrentFramerateSchema> | null;
    recentFrontendFrameDurations: number[]
    recentBackendFrameDurations: number[]
}

const initialState: FramerateState = {
    currentFrontendFramerate: null,
    currentBackendFramerate: null,
    recentFrontendFrameDurations: [],
    recentBackendFrameDurations: [],
}

export const framerateTrackerSlice = createSlice({
    name: 'framerate',
    initialState,
    reducers: {
        setFrontendFramerate: (state, action: PayloadAction<FramerateData>) => {
            // Map the gRPC FramerateData to our CurrentFramerate format
            const mappedFramerate = mapFramerateDataToCurrentFramerate(action.payload);
            state.currentFrontendFramerate = CurrentFramerateSchema.parse(mappedFramerate);

            // Keep a rolling list of recent framerates
            state.recentFrontendFrameDurations.push(state.currentFrontendFramerate.frame_duration_median);
            if (state.recentFrontendFrameDurations.length > MAX_FRAMERATE_ENTRIES) {
                state.recentFrontendFrameDurations.shift();
            }
        },
        setBackendFramerate: (state, action: PayloadAction<FramerateData>) => {
            // Map the gRPC FramerateData to our CurrentFramerate format
            const mappedFramerate = mapFramerateDataToCurrentFramerate(action.payload);
            state.currentBackendFramerate = CurrentFramerateSchema.parse(mappedFramerate);

            // Keep a rolling list of recent framerates
            state.recentBackendFrameDurations.push(state.currentBackendFramerate.frame_duration_median);
            if (state.recentBackendFrameDurations.length > MAX_FRAMERATE_ENTRIES) {
                state.recentBackendFrameDurations.shift();
            }
        },
        // combined setter for both framerates
        updateFramerates: (state, action: PayloadAction<FramerateUpdate>) => {
            const { backendFramerate, frontendFramerate } = action.payload;

            // Update backend framerate if provided
            if (backendFramerate) {
                const mappedBackendFramerate = mapFramerateDataToCurrentFramerate(backendFramerate);
                state.currentBackendFramerate = CurrentFramerateSchema.parse(mappedBackendFramerate);

                // Keep a rolling list of recent framerates
                state.recentBackendFrameDurations.push(state.currentBackendFramerate.frame_duration_median);
                if (state.recentBackendFrameDurations.length > MAX_FRAMERATE_ENTRIES) {
                    state.recentBackendFrameDurations.shift();
                }
            }

            // Update frontend framerate if provided
            if (frontendFramerate) {
                const mappedFrontendFramerate = mapFramerateDataToCurrentFramerate(frontendFramerate);
                state.currentFrontendFramerate = CurrentFramerateSchema.parse(mappedFrontendFramerate);

                // Keep a rolling list of recent framerates
                state.recentFrontendFrameDurations.push(state.currentFrontendFramerate.frame_duration_median);
                if (state.recentFrontendFrameDurations.length > MAX_FRAMERATE_ENTRIES) {
                    state.recentFrontendFrameDurations.shift();
                }
            }
        }
    }
})


export const {setFrontendFramerate, setBackendFramerate, updateFramerates} = framerateTrackerSlice.actions
export default framerateTrackerSlice.reducer
