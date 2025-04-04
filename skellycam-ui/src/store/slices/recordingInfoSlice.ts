// recordingInfoSlice.ts
import {createSlice, PayloadAction} from '@reduxjs/toolkit'
import {z} from 'zod';

export const getDefaultRecordingDirectory = async () => {
    const homePath =   await window.electronAPI.getHomeDirectory()
    const defaultSkellycamDataHFolder =  '/skellycam_data/recordings';
    return `${homePath}${defaultSkellycamDataHFolder}`;
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
        recordingDirectory: await getDefaultRecordingDirectory(),
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
