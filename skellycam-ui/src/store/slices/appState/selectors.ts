// src/store/slices/appState/selectors.ts
import {createSelector} from '@reduxjs/toolkit';
import {RootState} from '@/store/appStateStore';

export const selectIsRecording = (state: RootState) => state.appState.isRecording;
export const selectFrameRate = (state: RootState) => state.appState.framerate;

export const selectFormattedFrameRate = createSelector(
    [selectFrameRate],
    (frameRate) => frameRate ? `${frameRate.recent_frames_per_second.toFixed(1)} FPS` : '--'
);
