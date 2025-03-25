// recordingInfoSlice.ts
import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {z} from 'zod';

export const getDefaultRecordingDirectory = (): string => {
    return '~/skellycam_data/recordings';
};

// Simplified schema to match server expectations
export const RecordingInfoSchema = z.object({
    isRecording: z.boolean(),
    recordingDirectory: z.string(),
    recordingName: z.string().nullable(),
});

export type RecordingInfo = z.infer<typeof RecordingInfoSchema>;

interface RecordingStatusState {
    currentRecordingInfo: RecordingInfo;
}

const initialState: RecordingStatusState = {
    currentRecordingInfo: RecordingInfoSchema.parse({
        isRecording: false,
        recordingDirectory: getDefaultRecordingDirectory(),
        recordingName: null,
    })
};

export const recordingInfoSlice = createSlice({
    name: 'recordingStatus',
    initialState,
    reducers: {
        setRecordingInfo: (state, action: PayloadAction<Partial<RecordingInfo>>) => {
            console.log('Updating recording info:', action.payload);
            state.currentRecordingInfo = {
                ...state.currentRecordingInfo,
                ...action.payload
            };
        },
    }
});

export const {setRecordingInfo} = recordingInfoSlice.actions;
export default recordingInfoSlice.reducer;