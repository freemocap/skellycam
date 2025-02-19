import { createAsyncThunk } from '@reduxjs/toolkit';
import {setIsRecording} from "@/store/slices/appState";

export const startRecording = createAsyncThunk(
    'appState/startRecording',
    async (_, { dispatch }) => {
        try {
            //TODO -get this URL from on high
            const response = await fetch('http://localhost:8006/skellycam/cameras/record/start');
            if (response.ok) {
                dispatch(setIsRecording(true));
            }
        } catch (error) {
            console.error('Recording start failed:', error);
            throw error;
        }
    }
);

export const stopRecording = createAsyncThunk(
    'appState/stopRecording',
    async (_, { dispatch }) => {
        try {
            //TODO -get this URL from on high
            const response = await fetch('http://localhost:8006/skellycam/cameras/record/stop');
            if (response.ok) {
                dispatch(setIsRecording(false));
            }
        } catch (error) {
            console.error('Recording stop failed:', error);
            throw error;
        }
    }
);
