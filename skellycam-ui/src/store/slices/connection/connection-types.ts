import { CameraConfig } from '@/store/slices/cameras/cameras-types';

/** One camera group as reported in the server's pushed APP_STATE snapshot. */
export interface CameraGroupSnapshot {
    id: string;
    configs: Record<string, CameraConfig>;
    cameras: Record<string, unknown>;
    alive: boolean;
    recording_in_progress: boolean;
    paused: boolean;
}

/** The `state` payload of an APP_STATE message. */
export interface AppStateSnapshot {
    camera_groups: Record<string, CameraGroupSnapshot>;
}

/** Full APP_STATE websocket message: the server's authoritative observed state,
 * pushed on connect and whenever it changes. */
export interface AppStateMessage {
    message_type: 'app_state';
    server_pid: number;
    state: AppStateSnapshot;
}

/** Connectedness + server identity, all derived from the websocket. */
export interface ConnectionState {
    isConnected: boolean;
    serverPid: number | null;
    cameraGroups: CameraGroupSnapshot[];
}
