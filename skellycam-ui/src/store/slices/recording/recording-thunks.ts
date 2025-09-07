import { createAsyncThunk } from '@reduxjs/toolkit';
import { z } from 'zod';
import {urlService} from "@/services/api";

const RecordStartRequestSchema = z.object({
    recording_name: z.string(),
    recording_directory: z.string(),
    mic_device_index: z.number().default(-1),
});

interface StartRecordingParams {
    recordingName: string;
    recordingDirectory: string;
    micDeviceIndex?: number;
}

export const startRecording = createAsyncThunk<void, StartRecordingParams>(
    'recording/start',
    async ({ recordingName, recordingDirectory, micDeviceIndex = -1 }) => {
        const payload = RecordStartRequestSchema.parse({
            recording_name: recordingName,
            recording_directory: recordingDirectory,
            mic_device_index: micDeviceIndex,
        });

        const response = await fetch(urlService.endpoints.startRecording, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            throw new Error(`Failed to start recording: ${response.statusText}`);
        }
    }
);

export const stopRecording = createAsyncThunk<void>(
    'recording/stop',
    async () => {
        const response = await fetch(urlService.endpoints.stopRecording, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Failed to stop recording: ${response.statusText}`);
        }
    }
);
