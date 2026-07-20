import { RootState } from '../../types';

export const selectIsServerConnected = (state: RootState) => state.connection.isConnected;
export const selectServerPid = (state: RootState) => state.connection.serverPid;
export const selectCameraGroups = (state: RootState) => state.connection.cameraGroups;
