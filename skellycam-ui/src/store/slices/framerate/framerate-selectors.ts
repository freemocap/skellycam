import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';

export const selectFrontendFramerate = (state: RootState) =>
    state.framerate.currentFrontendFramerate;
export const selectBackendFramerate = (state: RootState) =>
    state.framerate.currentBackendFramerate;

export const selectAverageFramerates = createSelector(
    [
        (state: RootState) => state.framerate.recentFrontendFrameDurations,
        (state: RootState) => state.framerate.recentBackendFrameDurations,
    ],
    (frontendDurations, backendDurations) => {
        const calcAverage = (durations: number[]) => {
            if (durations.length === 0) return 0;
            const sum = durations.reduce((a, b) => a + b, 0);
            return 1000 / (sum / durations.length); // Convert to FPS
        };

        return {
            frontend: calcAverage(frontendDurations),
            backend: calcAverage(backendDurations),
        };
    }
);
