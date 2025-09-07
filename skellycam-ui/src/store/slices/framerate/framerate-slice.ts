import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface FramerateData {
    mean: number;
    std: number;
    current: number;
}

interface FramerateState {
    backend: FramerateData | null;
    frontend: FramerateData | null;
}

const initialState: FramerateState = {
    backend: null,
    frontend: null,
};

export const framerateSlice = createSlice({
    name: 'framerate',
    initialState,
    reducers: {
        backendFramerateUpdated: (state, action: PayloadAction<FramerateData>) => {
            state.backend = action.payload;
        },
        frontendFramerateUpdated: (state, action: PayloadAction<FramerateData>) => {
            state.frontend = action.payload;
        },
    },
});

export const { backendFramerateUpdated, frontendFramerateUpdated } = framerateSlice.actions;
