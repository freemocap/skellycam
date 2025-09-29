// cameras-slice.ts
import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import {
    Camera,
    CamerasState,
    CameraConfig,
    createDefaultCameraConfig,
    areConfigsEqual,
    extractConfigSettings
} from './cameras-types';
import {
    detectCameras,
    connectToCameras,
    updateCameraConfigs,
    closeCameras,
} from './cameras-thunks';

const initialState: CamerasState = {
    cameras: [],
    isLoading: false,
    error: null,
};

export const cameraSlice = createSlice({
    name: 'cameras',
    initialState,
    reducers: {
        // ========== Camera Management ==========
        cameraAdded: (state, action: PayloadAction<Camera>) => {
            const existingIndex = state.cameras.findIndex(
                cam => cam.id === action.payload.id
            );

            if (existingIndex >= 0) {
                state.cameras[existingIndex] = action.payload;
            } else {
                state.cameras.push(action.payload);
            }
        },

        cameraRemoved: (state, action: PayloadAction<string>) => {
            state.cameras = state.cameras.filter(cam => cam.id !== action.payload);
        },

        // ========== Selection ==========
        cameraSelectionToggled: (state, action: PayloadAction<string>) => {
            const camera = state.cameras.find(cam => cam.id === action.payload);
            if (camera) {
                camera.selected = !camera.selected;
                camera.desiredConfig.use_this_camera = camera.selected;
            }
        },

        allCamerasSelected: (state) => {
            state.cameras.forEach(camera => {
                camera.selected = true;
                camera.desiredConfig.use_this_camera = true;
            });
        },

        allCamerasDeselected: (state) => {
            state.cameras.forEach(camera => {
                camera.selected = false;
                camera.desiredConfig.use_this_camera = false;
            });
        },

        // ========== Configuration ==========
        // User updates desired config
        cameraDesiredConfigUpdated: (
            state,
            action: PayloadAction<{
                cameraId: string;
                config: Partial<CameraConfig>
            }>
        ) => {
            const camera = state.cameras.find(
                cam => cam.id === action.payload.cameraId
            );
            if (camera) {
                camera.desiredConfig = { ...camera.desiredConfig, ...action.payload.config };
                // Check if there's now a mismatch
                camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
            }
        },

        // Actual config updated from stream
        cameraActualConfigUpdated: (
            state,
            action: PayloadAction<{
                cameraId: string;
                config: CameraConfig
            }>
        ) => {
            const camera = state.cameras.find(
                cam => cam.id === action.payload.cameraId
            );
            if (camera) {
                camera.actualConfig = action.payload.config;
                // Check if there's a mismatch with desired
                camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
            }
        },

        // Apply desired config to actual (when user clicks "apply" button)
        applyDesiredConfigToActual: (state, action: PayloadAction<string>) => {
            const camera = state.cameras.find(cam => cam.id === action.payload);
            if (camera) {
                // This will trigger the API call to update the camera
                // The actual config will be updated when we receive it from stream
                camera.hasConfigMismatch = false;
            }
        },

        // Reset desired config to match actual
        resetDesiredConfigToActual: (state, action: PayloadAction<string>) => {
            const camera = state.cameras.find(cam => cam.id === action.payload);
            if (camera) {
                camera.desiredConfig = { ...camera.actualConfig };
                camera.hasConfigMismatch = false;
            }
        },

        configCopiedToAll: (state, action: PayloadAction<string>) => {
            const sourceCamera = state.cameras.find(cam => cam.id === action.payload);
            if (!sourceCamera) return;

            // Extract copyable settings (exclude identity fields)
            const settings = extractConfigSettings(sourceCamera.desiredConfig);

            state.cameras.forEach(camera => {
                if (camera.id !== action.payload) {
                    camera.desiredConfig = {
                        ...camera.desiredConfig,
                        ...settings
                    };
                    camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
                }
            });
        },

        // ========== Metrics (from WebSocket) ==========
        cameraMetricsUpdated: (
            state,
            action: PayloadAction<{
                cameraId: string;
                fps: number;
                droppedFrames: number;
                lastFrameTime: number;
            }>
        ) => {
            const camera = state.cameras.find(
                cam => cam.id === action.payload.cameraId
            );
            if (camera) {
                camera.metrics = {
                    fps: action.payload.fps,
                    droppedFrames: action.payload.droppedFrames,
                    lastFrameTime: action.payload.lastFrameTime,
                };
            }
        },

        // ========== Cameras from WebSocket Stream ==========
        camerasDetectedFromStream: (state, action: PayloadAction<CameraConfig[]>) => {
            action.payload.forEach(config => {
                const exists = state.cameras.some(cam => cam.id === config.camera_id);
                if (!exists) {
                    state.cameras.push({
                        id: config.camera_id,
                        index: config.camera_index,
                        name: config.camera_name,
                        actualConfig: config,
                        desiredConfig: { ...config },  // Start with desired = actual
                        hasConfigMismatch: false,
                        connectionStatus: 'connected',
                        selected: true,
                        deviceInfo: {},
                    });
                }
            });
        },

        // Batch update actual configs from stream
        actualConfigsUpdatedFromStream: (
            state,
            action: PayloadAction<Map<string, CameraConfig>>
        ) => {
            action.payload.forEach((config: CameraConfig, cameraId: string) => {
                const camera = state.cameras.find(cam => cam.id === cameraId);
                if (camera) {
                    camera.actualConfig = config;
                    camera.hasConfigMismatch = !areConfigsEqual(camera.actualConfig, camera.desiredConfig);
                }
            });
        },

        // ========== Error Handling ==========
        errorCleared: (state) => {
            state.error = null;
        },
    },

    extraReducers: (builder) => {
        builder
            // ========== Detect Cameras ==========
            .addCase(detectCameras.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(detectCameras.fulfilled, (state, action) => {
                state.isLoading = false;
                state.cameras = action.payload;
            })
            .addCase(detectCameras.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to detect cameras';
            })

            // ========== Connect Cameras ==========
            .addCase(connectToCameras.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(connectToCameras.fulfilled, (state, action) => {
                state.isLoading = false;
                // Update both actual and desired configs from server response
                Object.entries(action.payload.camera_configs).forEach(
                    ([cameraId, config]) => {
                        const camera = state.cameras.find(cam => cam.id === cameraId);
                        if (camera) {
                            camera.actualConfig = config as CameraConfig;
                            camera.desiredConfig = { ...config as CameraConfig };
                            camera.hasConfigMismatch = false;
                            camera.connectionStatus = 'connected';
                        }
                    }
                );
            })
            .addCase(connectToCameras.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to connect to cameras';
            })

            // ========== Update Configs ==========
            .addCase(updateCameraConfigs.pending, (state) => {
                state.isLoading = true;
            })
            .addCase(updateCameraConfigs.fulfilled, (state, action) => {
                state.isLoading = false;
                // When configs are successfully updated, sync desired to actual
                Object.entries(action.payload.camera_configs).forEach(
                    ([cameraId, config]) => {
                        const camera = state.cameras.find(cam => cam.id === cameraId);
                        if (camera) {
                            camera.actualConfig = config as CameraConfig;
                            camera.desiredConfig = { ...config as CameraConfig };
                            camera.hasConfigMismatch = false;
                        }
                    }
                );
            })
            .addCase(updateCameraConfigs.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to update camera configs';
            })

            // ========== Close Cameras ==========
            .addCase(closeCameras.fulfilled, (state) => {
                state.cameras.forEach(camera => {
                    camera.connectionStatus = 'available';
                    camera.metrics = undefined;
                    camera.hasConfigMismatch = false;
                });
            });
    },
});

export const {
    cameraSelectionToggled,
    allCamerasSelected,
    allCamerasDeselected,
    cameraDesiredConfigUpdated,
    cameraActualConfigUpdated,
    applyDesiredConfigToActual,
    resetDesiredConfigToActual,
    configCopiedToAll,
    cameraMetricsUpdated,
    camerasDetectedFromStream,
    actualConfigsUpdatedFromStream,
    errorCleared,
} = cameraSlice.actions;
