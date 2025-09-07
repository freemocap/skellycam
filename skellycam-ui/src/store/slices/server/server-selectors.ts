import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';

export const selectServerStatus = (state: RootState) => state.server.status;
export const selectServerConfig = (state: RootState) => state.server.config;
export const selectServerError = (state: RootState) => state.server.errorMessage;
export const selectServerProcessInfo = (state: RootState) => state.server.processInfo;

export const selectIsServerAlive = createSelector(
    [selectServerStatus],
    (status) => status === 'alive'
);

export const selectIsServerTransitioning = createSelector(
    [selectServerStatus],
    (status) => status === 'spawning' || status === 'shutting-down'
);

export const selectServerUrls = createSelector(
    [selectServerConfig],
    (config) => ({
        http: `http://${config.host}:${config.port}`,
        websocket: `ws://${config.host}:${config.port}/skellycam/websocket/connect`,
    })
);
