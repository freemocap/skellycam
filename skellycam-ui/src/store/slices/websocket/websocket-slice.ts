import { createSlice, PayloadAction } from '@reduxjs/toolkit';

// NOTE - No binary data in the Redux store, metadata only!

export type WebSocketStatus =
    | 'disconnected'
    | 'connecting'
    | 'connected'
    | 'reconnecting'
    | 'error';

interface FrameMetadata {
    cameraId: string;
    frameNumber: number;
    timestamp: number;
    width: number;
    height: number;
}

interface WebSocketState {
    status: WebSocketStatus;
    error: string | null;
    reconnectAttempt: number;
    shouldReconnect: boolean;
    lastConnectedAt: string | null;
    lastDisconnectedAt: string | null;
    // Only metadata, no binary data
    frameMetadata: Record<string, FrameMetadata>;
}

const initialState: WebSocketState = {
    status: 'disconnected',
    error: null,
    reconnectAttempt: 0,
    shouldReconnect: true,
    lastConnectedAt: null,
    lastDisconnectedAt: null,
    frameMetadata: {},
};

export const websocketSlice = createSlice({
    name: 'websocket',
    initialState,
    reducers: {
        websocketStatusChanged: (state, action: PayloadAction<WebSocketStatus>) => {
            state.status = action.payload;
            state.error = null;

            if (action.payload === 'connected') {
                state.lastConnectedAt = new Date().toISOString();
                state.reconnectAttempt = 0;
            } else if (action.payload === 'disconnected') {
                state.lastDisconnectedAt = new Date().toISOString();
            }
        },
        websocketErrorOccurred: (state, action: PayloadAction<string>) => {
            state.status = 'error';
            state.error = action.payload;
        },
        websocketReconnectAttempted: (state) => {
            state.status = 'reconnecting';
            state.reconnectAttempt += 1;
        },
        frameMetadataUpdated: (state, action: PayloadAction<FrameMetadata>) => {
            state.frameMetadata[action.payload.cameraId] = action.payload;
        },
    },
});

export const {
    websocketStatusChanged,
    websocketErrorOccurred,
    websocketReconnectAttempted,
    frameMetadataUpdated,
} = websocketSlice.actions;
