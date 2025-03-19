import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {z} from 'zod';

export const RecordingInfoSchema = z.object({
    isRecording: z.boolean(),
    recordingDirectory: z.string().nullable()
});
export type RecordingInfo = z.infer<typeof RecordingInfoSchema>;

interface RecordingStatusState {
    currentRecordingInfo: RecordingInfo | null;
}

const initialState: RecordingStatusState = {
    currentRecordingInfo: RecordingInfoSchema.parse({
        isRecording: false,
        recordingDirectory: null
    })
}

export const recordingInfoSlice = createSlice({
    name: 'recordingStatus',
    initialState,
    reducers: {
        setRecordingInfo: (state, action: PayloadAction<RecordingInfo>) => {
            state.currentRecordingInfo = RecordingInfoSchema.parse(action.payload);
        }
    }
})

export const {setRecordingInfo} = recordingInfoSlice.actions
export default recordingInfoSlice.reducer
