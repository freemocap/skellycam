/**
 * TypeScript type definitions for SkellyCam SDK
 * Matches Python Pydantic models for type-safe integration
 */

export interface CameraConfig {
  camera_id: string;
  name?: string;
  resolution?: [number, number];
  fps?: number;
  pixel_format?: string;
  backend?: string;
  options?: Record<string, unknown>;
}

export interface RecordingSession {
  session_id: string;
  name: string;
  start_time: string;
  end_time?: string;
  camera_configs: CameraConfig[];
  recording_path: string;
  is_recording: boolean;
  frame_count: number;
  metadata?: Record<string, unknown>;
}

export interface CameraFrame {
  camera_id: string;
  frame_number: number;
  timestamp_ns: number;
  image_data?: string;
  width: number;
  height: number;
}

export interface FramePayload {
  frame_number: number;
  timestamp_ns: number;
  camera_frames: CameraFrame[];
  is_keyframe?: boolean;
}

export type WebSocketMessageType =
  | 'frame'
  | 'camera_connected'
  | 'camera_disconnected'
  | 'recording_started'
  | 'recording_stopped'
  | 'error'
  | 'config_update';

export interface BaseWebSocketMessage {
  type: WebSocketMessageType;
  timestamp: number;
}

export interface FrameWebSocketMessage extends BaseWebSocketMessage {
  type: 'frame';
  payload: FramePayload;
}

export interface CameraStatusWebSocketMessage extends BaseWebSocketMessage {
  type: 'camera_connected' | 'camera_disconnected';
  payload: {
    camera_id: string;
    config: CameraConfig;
  };
}

export interface RecordingStatusWebSocketMessage extends BaseWebSocketMessage {
  type: 'recording_started' | 'recording_stopped';
  payload: {
    session_id: string;
    timestamp: string;
  };
}

export interface ErrorWebSocketMessage extends BaseWebSocketMessage {
  type: 'error';
  payload: {
    code: string;
    message: string;
    camera_id?: string;
  };
}

export interface ConfigUpdateWebSocketMessage extends BaseWebSocketMessage {
  type: 'config_update';
  payload: {
    cameras: CameraConfig[];
  };
}

export type WebSocketMessage =
  | FrameWebSocketMessage
  | CameraStatusWebSocketMessage
  | RecordingStatusWebSocketMessage
  | ErrorWebSocketMessage
  | ConfigUpdateWebSocketMessage;
