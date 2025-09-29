// cameras-types.ts
import { z } from 'zod';

// ==================== Constants ====================
export const PIXEL_FORMATS = ['RGB', 'BGR', 'GRAY'] as const;
export const EXPOSURE_MODES = ['MANUAL', 'AUTO', 'RECOMMEND'] as const;
export const CONNECTION_STATUS = ['disconnected', 'connecting', 'connected', 'error'] as const;
export const ROTATION_OPTIONS = ['None', '90', '180', '270'] as const;
export const FOURCC_OPTIONS = ['MJPG', 'X264', 'YUYV', 'H264'] as const;

export type PixelFormat = typeof PIXEL_FORMATS[number];
export type ExposureMode = typeof EXPOSURE_MODES[number];
export type ConnectionStatus = typeof CONNECTION_STATUS[number];
export type RotationOption = typeof ROTATION_OPTIONS[number];
export type FourccOption = typeof FOURCC_OPTIONS[number];

// ==================== Camera Configuration ====================
export const CameraConfigSchema = z.object({
    // Identity
    camera_id: z.string(),
    camera_index: z.number(),
    camera_name: z.string(),
    use_this_camera: z.boolean(),

    // Video settings
    resolution: z.object({
        width: z.number().int(),
        height: z.number().int()
    }),
    framerate: z.number().min(1).max(1000),

    // Image settings
    color_channels: z.number().int().min(1).max(4),
    pixel_format: z.enum(PIXEL_FORMATS),
    rotation: z.enum(ROTATION_OPTIONS),

    // Exposure settings
    exposure_mode: z.enum(EXPOSURE_MODES),
    exposure: z.number(),

    // Codec settings
    capture_fourcc: z.enum(FOURCC_OPTIONS),
    writer_fourcc: z.enum(FOURCC_OPTIONS),
});

export type CameraConfig = z.infer<typeof CameraConfigSchema>;

// ==================== Camera State ====================
export interface Camera {
    id: string;                    // Primary key (same as camera_id in config) - must be unique
    index: number;                 // Device index, e.g. the port number used in cv2.VideoCapture() - must be unique
    name: string;                  // Human-readable name, e.g. "Logitech C920" - not necessarily unique
    actualConfig: CameraConfig;     // Configuration extracted from camera stream
    desiredConfig: CameraConfig;    // User's desired configuration
    hasConfigMismatch: boolean;     // Whether actual differs from desired
    connectionStatus: 'available' | 'connected' | 'error';  // Connection state
    selected: boolean;              // UI selection state

    // Device info (from detection)
    deviceInfo: {
        virtual?: boolean;
        vendorId?: string;
        productId?: string;
    };

    // Performance metrics (optional, updated from websocket)
    metrics?: {
        fps: number;
        droppedFrames: number;
        lastFrameTime: number;
    };
}

// ==================== Store State ====================
export interface CamerasState {
    cameras: Camera[];
    isLoading: boolean;
    error: string | null;
}

// ==================== API Types ====================
export interface DetectCamerasRequest {
    filterVirtual?: boolean;
}

export interface DetectCamerasResponse {
    cameras: Array<{
        index: number;
        name: string;
        vendor_id?: string;
        product_id?: string;
    }>;
}

export interface ConnectCamerasRequest {
    camera_configs: Record<string, CameraConfig>;
}

export interface ConnectCamerasResponse {
    camera_configs: Record<string, CameraConfig>;
}

// ==================== Helper Functions ====================
export function createDefaultCameraConfig(
    id: string,
    index: number,
    name: string,
): CameraConfig {
    return {
        camera_id: id,
        camera_index: index,
        camera_name: name,
        use_this_camera: true,
        resolution: { width: 1280, height: 720 },
        framerate: 30,
        color_channels: 3,
        pixel_format: 'RGB',
        rotation: 'None',
        exposure_mode: 'AUTO',
        exposure: -7,
        capture_fourcc: 'MJPG',
        writer_fourcc: 'X264',
    };
}
