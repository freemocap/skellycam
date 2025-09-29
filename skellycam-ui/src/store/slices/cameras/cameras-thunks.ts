// cameras-thunks.ts
import { createAsyncThunk } from '@reduxjs/toolkit';
import { RootState } from '../../types';
import { serverUrls } from '@/services';
import {
    Camera,
    CameraConfig,
    DetectCamerasRequest,
    DetectCamerasResponse,
    ConnectCamerasRequest,
    ConnectCamerasResponse,
    createDefaultCameraConfig,
} from './cameras-types';
import { selectSelectedCameraConfigs } from './cameras-selectors';

export const detectCameras = createAsyncThunk<
    Camera[],
    DetectCamerasRequest | undefined,
    { state: RootState }
>(
    'cameras/detect',
    async (request = { filterVirtual: true }, { getState }) => {
        const state = getState();
        const existingCameras = state.cameras.cameras;

        const response = await fetch(serverUrls.endpoints.detectCameras, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error(`Failed to detect cameras: ${response.statusText}`);
        }

        const data: DetectCamerasResponse = await response.json();

        return data.cameras.map((serverCamera): Camera => {
            const cameraId = serverCamera.index.toString();
            const existing = existingCameras.find(cam => cam.id === cameraId);

            const defaultConfig = createDefaultCameraConfig(
                cameraId,
                serverCamera.index,
                serverCamera.name,
            );

            return {
                id: cameraId,
                name: serverCamera.name,
                index: serverCamera.index,
                // If camera exists, preserve its configs, otherwise use defaults
                actualConfig: existing?.actualConfig || defaultConfig,
                desiredConfig: existing?.desiredConfig || { ...defaultConfig },
                hasConfigMismatch: existing?.hasConfigMismatch ?? false,
                connectionStatus: 'available',
                selected: existing?.selected ?? true,
                deviceInfo: {
                    vendorId: serverCamera.vendor_id,
                    productId: serverCamera.product_id,
                },
                metrics: existing?.metrics,
            };
        });
    }
);

export const connectToCameras = createAsyncThunk<
    ConnectCamerasResponse,
    void,
    { state: RootState }
>(
    'cameras/connect',
    async (_, { getState }) => {
        const state = getState();
        const cameraConfigs = selectSelectedCameraConfigs(state);

        if (Object.keys(cameraConfigs).length === 0) {
            throw new Error('No cameras selected for connection');
        }

        const request: ConnectCamerasRequest = { camera_configs: cameraConfigs };

        const response = await fetch(serverUrls.endpoints.createGroup, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to connect to cameras');
        }

        return response.json() as Promise<ConnectCamerasResponse>;
    }
);

export const updateCameraConfigs = createAsyncThunk<
    ConnectCamerasResponse,
    void,
    { state: RootState }
>(
    'cameras/updateConfigs',
    async (_, { getState }) => {
        const state = getState();
        const cameraConfigs = selectSelectedCameraConfigs(state);

        const request: ConnectCamerasRequest = { camera_configs: cameraConfigs };

        const response = await fetch(serverUrls.endpoints.updateConfigs, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update camera configs');
        }

        return response.json() as Promise<ConnectCamerasResponse>;
    }
);

// New thunk to apply a single camera's desired config
export const applyCameraConfig = createAsyncThunk<
    ConnectCamerasResponse,
    string,  // camera ID
    { state: RootState }
>(
    'cameras/applyConfig',
    async (cameraId, { getState }) => {
        const state = getState();
        const camera = state.cameras.cameras.find(cam => cam.id === cameraId);

        if (!camera) {
            throw new Error(`Camera ${cameraId} not found`);
        }

        const request: ConnectCamerasRequest = {
            camera_configs: {
                [cameraId]: camera.desiredConfig
            }
        };

        const response = await fetch(serverUrls.endpoints.updateConfigs, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `Failed to apply config for camera ${cameraId}`);
        }

        return response.json() as Promise<ConnectCamerasResponse>;
    }
);

export const closeCameras = createAsyncThunk<void, void, { state: RootState }>(
    'cameras/close',
    async () => {
        const response = await fetch(serverUrls.endpoints.closeAll, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to close cameras: ${response.statusText}`);
        }
    }
);

export const pauseUnpauseCameras = createAsyncThunk<void, void, { state: RootState }>(
    'cameras/pause',
    async () => {
        const response = await fetch(serverUrls.endpoints.pauseUnpauseCameras, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Failed to pause/unpause cameras: ${response.statusText}`);
        }
    }
);
