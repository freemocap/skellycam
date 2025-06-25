import {createAsyncThunk} from "@reduxjs/toolkit";

export const pauseRecording = createAsyncThunk<void, void>(
    'appState/pauseRecording',
    async (_, ) => {
        console.log('Pausing...');
        try {
            const pauseUrl = 'http://localhost:8006/skellycam/camera/group/all/pause';
            const response = await fetch(pauseUrl, {
                method: 'GET',
            });

            if (response.ok) {
                console.log('Paused successfully');
            } else {
                throw new Error(`Faild to Pause: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Pause failed:', error);
            throw error;
        }
    }
);

export const unpauseRecording = createAsyncThunk<void, void>(
    'appState/unpauseRecording',
    async (_, ) => {
        console.log('Unpausing...');
        try {
            const unpauseUrl = 'http://localhost:8006/skellycam/camera/group/all/unpause';
            const response = await fetch(unpauseUrl, {
                method: 'GET',
            });

            if (response.ok) {

                console.log('Unpaused successfully');
            } else {
                throw new Error(`Failed to unpause: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Unpause failed:', error);
            throw error;
        }
    }
);
