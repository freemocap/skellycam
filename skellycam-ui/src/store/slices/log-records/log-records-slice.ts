import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface LogRecord {
    name: string;
    msg: string | null;
    levelname: string;
    levelno: number;
    message: string;
    asctime: string;
    [key: string]: any;
}

interface LogRecordsState {
    entries: LogRecord[];
    maxEntries: number;
}

const initialState: LogRecordsState = {
    entries: [],
    maxEntries: 1000,
};

export const logRecordsSlice = createSlice({
    name: 'logs',
    initialState,
    reducers: {
        logAdded: (state, action: PayloadAction<LogRecord>) => {
            state.entries.push(action.payload);
            if (state.entries.length > state.maxEntries) {
                state.entries = state.entries.slice(-state.maxEntries);
            }
        },
        logsCleared: (state) => {
            state.entries = [];
        },
    },
});

export const { logAdded, logsCleared } = logRecordsSlice.actions;
