
import { createSelector } from '@reduxjs/toolkit';
import { RootState } from '../../types';
import { logsSelectors } from './log-records-slice';

export const selectAllLogs = (state: RootState) =>
    logsSelectors.selectAll(state.logs);

export const selectLogsByLevel = createSelector(
    [selectAllLogs, (_: RootState, level: string) => level],
    (logs, level) => logs.filter(log => log.levelname === level)
);

export const selectRecentLogs = createSelector(
    [selectAllLogs, (_: RootState, count: number = 10) => count],
    (logs, count) => logs.slice(-count)
);
