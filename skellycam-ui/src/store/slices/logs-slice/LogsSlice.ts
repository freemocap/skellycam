import type {PayloadAction} from "@reduxjs/toolkit";
import {createSlice} from "@reduxjs/toolkit"

export type LogSeverity = "loop" | "trace" | "debug" | "info" | "success" | "warning" | "error" | "critical"

export interface LogEntry {
    timestamp: number
    message: string
    severity: LogSeverity
}

interface LogsState {
    entries: LogEntry[]
}

const initialState: LogsState = {
    entries: [],
}

export const logsSlice = createSlice({
    name: "logs",
    initialState,
    reducers: {
        addLog: (state,
                 action: PayloadAction<Omit<LogEntry, "timestamp">>) => {
            state.entries.push({
                timestamp: Date.now(),
                ...action.payload,
            })
        },
        clearLogs: (state) => {
            state.entries = []
        },
    },
})

export const {addLog, clearLogs} = logsSlice.actions
export default logsSlice.reducer
