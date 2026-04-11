import { createAsyncThunk } from '@reduxjs/toolkit';
import { RootState } from '@/store/types';
import { serverUrls } from '@/services';
import { RecordingCompletionData, StopRecordingResponseSchema } from './recording-types';

interface StartRecordingParams {
    recordingName: string;
    recordingDirectory: string;
    micDeviceIndex?: number;
}

export const startRecording = createAsyncThunk<
    void,
    StartRecordingParams,
    { state: RootState }
>(
    'recording/start',
    async ({ recordingName, recordingDirectory, micDeviceIndex = -1 }) => {
        const response = await fetch(serverUrls.endpoints.allCameraGroupsRecording, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                recording_name: recordingName,
                recording_directory: recordingDirectory,
                mic_device_index: micDeviceIndex,
            }),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `Failed to start recording: ${response.statusText}`);
        }
    }
);

export const stopRecording = createAsyncThunk<
    RecordingCompletionData | null,
    void,
    { state: RootState }
>(
    'recording/stop',
    async () => {
        const response = await fetch(serverUrls.endpoints.allCameraGroupsRecording, {
            method: 'DELETE',
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.detail || `Failed to stop recording: ${response.statusText}`);
        }

        const data = await response.json();
        // Response is { recordings: [...] } — take the first entry
        const recordings: unknown[] = data?.recordings ?? [];
        if (recordings.length === 0) {
            return null;
        }

        const parsed = StopRecordingResponseSchema.safeParse(recordings[0]);
        if (!parsed.success) {
            console.warn('Unexpected stop_recording response shape:', parsed.error);
            return null;
        }
        return parsed.data;
    }
);
