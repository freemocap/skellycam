import type {PayloadAction} from "@reduxjs/toolkit";
import {createSlice} from "@reduxjs/toolkit"
import {z} from "zod";
import { LogRecord as GrpcLogRecord } from '@/contexts/grpc-context/grpc_generated/skellycam';

// Updated to match the server's LogRecordModel
export const LogRecordSchema = z.object({
    name: z.string(),
    msg: z.string().nullable().default(""),
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
export type LogRecord = z.infer<typeof LogRecordSchema>;

export const IncomingLogsSchema = z.object({
    logs: z.array(LogRecordSchema),
});

export type IncomingLogs = z.infer<typeof IncomingLogsSchema>;

// Helper function to map from gRPC LogRecord to our application's LogRecord format
const mapGrpcLogRecordToLogRecord = (grpcLogRecord: GrpcLogRecord): LogRecord => ({
    name: grpcLogRecord.name,
    msg: grpcLogRecord.message,
    args: grpcLogRecord.args,
    levelname: grpcLogRecord.levelName,
    levelno: grpcLogRecord.levelNo,
    pathname: grpcLogRecord.pathname,
    filename: grpcLogRecord.filename,
    module: grpcLogRecord.module,
    exc_info: grpcLogRecord.excInfo,
    exc_text: grpcLogRecord.excText,
    stack_info: grpcLogRecord.stackInfo,
    lineno: grpcLogRecord.lineNo,
    funcName: grpcLogRecord.funcName,
    created: grpcLogRecord.created,
    msecs: grpcLogRecord.msecs,
    relativeCreated: grpcLogRecord.relativeCreated,
    thread: grpcLogRecord.thread,
    threadName: grpcLogRecord.threadName,
    processName: grpcLogRecord.processName,
    process: grpcLogRecord.process,
    delta_t: grpcLogRecord.deltaT,
    message: grpcLogRecord.formattedMessage,
    asctime: grpcLogRecord.asctime,
    formatted_message: grpcLogRecord.formattedMessage,
    type: grpcLogRecord.type
});

interface LogsState {
    entries: LogRecord[]
}
const initialLogRecord: LogRecord = {
    name: "initial",
    msg: "Log entry initialized",
    args: [],
    levelname: "DEBUG",
    levelno: 10,
    filename: "filename",
    pathname: "pathname",
    module: "module",
    exc_info: "exc_info",
    exc_text: "exc_text",
    stack_info: "stack_info",
    lineno: 0,
    funcName: "funcName",
    created: 0,
    msecs: 0,
    relativeCreated: 0,
    thread: 0,
    threadName: "threadName",
    processName: "processName",
    process: 0,
    delta_t: "0.000",
    message: "Initial log message",
    asctime: new Date().toISOString(),
    formatted_message: "Initial log message",
    type: "log",
}
const initialState: LogsState = {
    entries: [initialLogRecord],
}
const MAX_LOG_ENTRIES = 300
export const logRecordsSlice = createSlice({
    name: "logs",
    initialState,
    reducers: {
        // Original addLog action for backward compatibility
        addLog: (state, action: PayloadAction<LogRecord>) => {
            const newLogEntry: LogRecord = {
                ...action.payload,
            }

            // if we're at the limit, remove the oldest entry first
            if (state.entries.length >= MAX_LOG_ENTRIES) {
                state.entries.shift() // Remove the oldest log entry
            }

            state.entries.push(newLogEntry)
        },

        // New action that accepts a gRPC LogRecord directly
        addGrpcLog: (state, action: PayloadAction<GrpcLogRecord>) => {
            // Map the gRPC LogRecord to our application's LogRecord format
            const mappedLogRecord = mapGrpcLogRecordToLogRecord(action.payload);

            // if we're at the limit, remove the oldest entry first
            if (state.entries.length >= MAX_LOG_ENTRIES) {
                state.entries.shift() // Remove the oldest log entry
            }

            state.entries.push(mappedLogRecord)
        },

        addLogs: (state, action: PayloadAction<IncomingLogs>) => {
            const newLogs: LogRecord[] = action.payload.logs
            // Add new logs to the state, ensuring we don't exceed the max limit
            for (const log of newLogs) {
                const newLogEntry: LogRecord = {
                    ...log,
                }

                // if we're at the limit, remove the oldest entry first
                if (state.entries.length >= MAX_LOG_ENTRIES) {
                    state.entries.shift() // Remove the oldest log entry
                }

                state.entries.push(newLogEntry)
            }
        }
    },
})

export const {addLog, addGrpcLog, addLogs} = logRecordsSlice.actions
export default logRecordsSlice.reducer
