import {createAsyncThunk} from '@reduxjs/toolkit';
import {setIsRecording} from '@/store/slices/appState';
import {z} from 'zod';


const RecordStartRequestSchema = z.object({
    recording_name: z.string().optional().default(''),
    recording_path: z.string().optional().default('~/skellycam_data/recordings'),
    mic_device_index: z.number().default(-1),
})

export const startRecording = createAsyncThunk<void, void>(
    'appState/startRecording',
    async (_, {dispatch}) => {
        try {
            const recStartUrl = 'http://localhost:8006/skellycam/cameras/record/start';
            const requestPayload = RecordStartRequestSchema.parse({});
            console.log(`Sending request to ${recStartUrl} with payload:`, JSON.stringify(requestPayload, null, 2));

            const response = await fetch(recStartUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestPayload),
            });
            if (response.ok) {
                console.log('Recording start vrequest successful - recording started');
                dispatch(setIsRecording(true));
            } else {
                console.error('Recording start failed:', response.statusText);
            }
        } catch (error) {
            console.error('Recording start failed:', error);
            throw error;
        }
    }
);

export const stopRecording = createAsyncThunk<void, void>(
    'appState/stopRecording',
    async (_, {dispatch}) => {
        try {
            const recStopUrl = 'http://localhost:8006/skellycam/cameras/record/stop';
            console.log(`Sending request to ${recStopUrl}`);
            const response = await fetch(recStopUrl, {
                method: 'GET',
            });
            if (response.ok) {
                console.log('Recording stop request successful - recording stopped');
                dispatch(setIsRecording(false));
            } else {
                console.error('Recording stop failed:', response.statusText);
            }
        } catch (error) {
            console.error('Recording stop failed:', error);
            throw error;
        }
    }
);