import type {PayloadAction} from "@reduxjs/toolkit";
import {createSlice} from "@reduxjs/toolkit"
import { z } from "zod";

export type LogSeverity = "loop" | "trace" | "debug" | "info" | "success" | "warning" | "error" | "critical"
export const LogRecordSchema = z.object({
    name: z.string(),
    msg: z.string(),
    args: z.array(z.any()),
    levelname: z.string(),
    levelno: z.number(),
    pathname: z.string(),
    filename: z.string(),
    module: z.string(),
    exc_info: z.string().nullable(),
    exc_text: z.string().nullable(),
    stack_info: z.string().nullable(),
    lineno: z.number(),
    funcName: z.string(),
    created: z.number(),
    msecs: z.number(),
    relativeCreated: z.number(),
    thread: z.number(),
    threadName: z.string(),
    processName: z.string(),
    process: z.number(),
    delta_t: z.string(),
    message: z.string(),
    asctime: z.string(),
    formatted_message: z.string(),
    type: z.string(),
});

export interface LogEntry {
    timestamp: number
    message: string
    severity: LogSeverity
    // Adding more detailed information
    formatted_message: string // message as formatted by backend logger
    name: string
    rawMessage: string  // original message before formatting
    args: any[]
    pathname: string
    filename: string
    module: string
    lineNumber: number
    functionName: string
    threadName: string
    processName: string
    stackTrace: string | null
    delta_t: string
}
interface LogsState {
    entries: LogEntry[]
}

const initialState: LogsState = {
    entries: [],
}
const MAX_LOG_ENTRIES = 1000
export const logsSlice = createSlice({
    name: "logs",
    initialState,
    reducers: {
        addLog: (state,
                 action: PayloadAction<Omit<LogEntry, "timestamp">>) => {
            const newLogEntry: LogEntry = {
                ...action.payload,
                timestamp: Date.now(),
            }
            state.entries.push(newLogEntry)
            if (state.entries.length > MAX_LOG_ENTRIES) {
                state.entries.shift() // Remove the oldest log entry
            }
        },

    },
})

export const {addLog} = logsSlice.actions
export default logsSlice.reducer
