import type {PayloadAction} from '@reduxjs/toolkit'
import {createSlice} from '@reduxjs/toolkit'
import {z} from 'zod';
// import * as os from 'os';
// import * as path from 'path';

export const getDefaultRecordingDirectory = (): string => {
    // const homeDir = os.homedir();
    // return path.join(homeDir, 'skellycam_data', 'recordings');
    return '~/skellycam_data/recordings';
};

export const formatIncrementalNumber = (num: number, padding: number = 3): string => {
    return num.toString().padStart(padding, '0');
};



export const getTimestampRecordingName = (): string => {
    const now = new Date();
    return now.toISOString()
        .replace(/[:.]/g, '-')
        .replace('T', '_')
        .split('.')[0];
};

export const buildRecordingName = (
    baseName: string,
    useTimestamp: boolean,
    useIncrement: boolean,
    increment: number,
    incrementFormat: string,
    tag?: string
): string => {
    const parts: string[] = [];

    if (useTimestamp) {
        parts.push(getTimestampRecordingName());
    } else {
        parts.push(baseName);
    }

    if (tag) {
        parts.push(tag);
    }

    if (useIncrement) {
        const incrementStr = formatIncrementalNumber(increment, parseInt(incrementFormat) || 3);
        parts.push(incrementStr);
    }

    return parts.join('_');
};


export const RecordingInfoSchema = z.object({
    isRecording: z.boolean(),
    recordingDirectory: z.string(),
    recordingTag: z.string().nullable(),
    useTimestamp: z.boolean(),
    useIncrement: z.boolean(),
    currentIncrement: z.number(),
    incrementFormat: z.string(), // number of digits for padding
    baseName: z.string(),
});

export type RecordingInfo = z.infer<typeof RecordingInfoSchema>;

interface RecordingStatusState {
    currentRecordingInfo: RecordingInfo;
}

const initialState: RecordingStatusState = {
    currentRecordingInfo: RecordingInfoSchema.parse({
        isRecording: false,
        recordingDirectory: getDefaultRecordingDirectory(),
        recordingTag: null,
        useTimestamp: true,
        useIncrement: true,
        currentIncrement: 0,
        incrementFormat: '3',
        baseName: 'recording',
    })
};


export const recordingInfoSlice = createSlice({
    name: 'recordingStatus',
    initialState,
    reducers: {
        setRecordingInfo: (state, action: PayloadAction<Partial<RecordingInfo>>) => {
            state.currentRecordingInfo = {
                ...state.currentRecordingInfo,
                ...action.payload
            };
        },
        incrementCounter: (state) => {
            state.currentRecordingInfo.currentIncrement += 1;
        },
        resetCounter: (state) => {
            state.currentRecordingInfo.currentIncrement = 0;
        }
    }
});

export const {setRecordingInfo, incrementCounter, resetCounter} = recordingInfoSlice.actions;
export default recordingInfoSlice.reducer;
