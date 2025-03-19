import {createAsyncThunk} from '@reduxjs/toolkit';
import {z} from 'zod';
import {setRecordingInfo} from "@/store/slices/recordingInfoSlice";


export function getTimestampRecordingName() {
    const dateString = new Date().toISOString().split('.')[0].replace(/:/g, '-').replace('T', '_')
    return 'skellycam-' + dateString;
}

const RecordStartRequestSchema = z.object({
    recording_name: z.string(),
    recording_path: z.string().optional().default('~/skellycam_data/recordings'),
    mic_device_index: z.number().default(-1),// default to -1 for default mic
})
export const startRecording = createAsyncThunk<void, string>(
    'appState/startRecording',
    async  (recordingTag: string, {dispatch}) => {
        try {
            const recStartUrl = 'http://localhost:8006/skellycam/cameras/record/start';
            const timestampName = getTimestampRecordingName();
            const recordingName = recordingTag ? `${timestampName}_${recordingTag}` : timestampName;

            const requestPayload = RecordStartRequestSchema.parse({
                recording_name: recordingName,
                recording_path: '~/skellycam_data/recordings',
                mic_device_index: -1
            });

            const response = await fetch(recStartUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestPayload),
            });

            if (response.ok) {
                dispatch(setRecordingInfo({
                    isRecording: true,
                    recordingDirectory: requestPayload.recording_path,
                    recordingTag: recordingTag
                }));
            } else {
                throw new Error(`Failed to start recording: ${response.statusText}`);
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
            const response = await fetch(recStopUrl, {
                method: 'GET',
            });

            if (response.ok) {
                dispatch(setRecordingInfo({
                    isRecording: false,
                    recordingDirectory: null,
                    recordingTag: null
                }));
            } else {
                throw new Error(`Failed to stop recording: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Recording stop failed:', error);
            throw error;
        }
    }
);
