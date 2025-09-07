import { createSelector } from '@reduxjs/toolkit';
import { RootState } from "../../types";

export const selectWebSocketStatus = (state: RootState) => state.websocket.status;
export const selectWebSocketError = (state: RootState) => state.websocket.error;
export const selectFrameMetadata = (state: RootState) => state.websocket.frameMetadata;

export const selectIsWebSocketConnected = createSelector(
    [selectWebSocketStatus],
    (status) => status === 'connected'
);

export const selectCameraFrameMetadata = (state: RootState, cameraId: string) =>
    state.websocket.frameMetadata[cameraId];
