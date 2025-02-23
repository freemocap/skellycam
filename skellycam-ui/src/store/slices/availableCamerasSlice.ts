import {AvailableCamerasSchema} from '@/types/zod-schemas/AvailableCamerasSchema';
import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {z} from 'zod';

export interface AvailableDevicesState {
    available_cameras: z.infer<typeof AvailableCamerasSchema> | null;
}

const initialState: AvailableDevicesState = {
    available_cameras: null,
}

export const availableCamerasSlice = createSlice({
    name: 'availableDevices',
    initialState,
    reducers: {
        setAvailableCameras: (state, action: PayloadAction<z.infer<typeof AvailableCamerasSchema> >) => {
            state.available_cameras = action.payload
        },
    },
})

// Action creators are generated for each case reducer function
export const { setAvailableCameras } = availableCamerasSlice.actions

export default availableCamerasSlice.reducer
