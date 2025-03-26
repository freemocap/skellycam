import { z } from 'zod';
export interface SerializedMediaDeviceInfo {
    index: number;
    deviceId: string;
    groupId: string;
    kind: string;
    label: string;
    selected: boolean;
}

// First define all the constant configurations
export const CAMERA_DEFAULTS = {
    resolution: {
        min: { width: 640, height: 480 },
        max: { width: 1920, height: 1080 },
        default: { width: 1280, height: 720 },
        presets: [
            { width: 640, height: 480, label: "VGA (4:3)" },
            { width: 1280, height: 720, label: "HD 720p (16:9)" },
            { width: 1920, height: 1080, label: "Full HD 1080p(16:9)" }
        ]
    },
    exposure: {
        min: -12,
        max: -5,
        default: -7,
        step: 1
    },
    framerate: {
        min: 1,
        max: 60,
        default: 30,
        available: [15, 30, 60]
    },
    pixel_formats: ['RGB', 'BGR', 'GRAY'] as const,
    exposure_modes: ['MANUAL', 'AUTO','RECOMMEND' ] as const,
    rotation_options: ['0', '90', '180', '270'] as const,
    fourcc_options: [ 'X264','MJPG', 'YUYV', 'H264'] as const
} as const;

// Then define your schemas based on these constants
export const ResolutionPresetSchema = z.object({
    width: z.number().int(),
    height: z.number().int(),
    label: z.string()
});

export const ExposureModeSchema = z.enum(CAMERA_DEFAULTS.exposure_modes);
export const RotationOptionSchema = z.enum(CAMERA_DEFAULTS.rotation_options);
export const PixelFormatSchema = z.enum(CAMERA_DEFAULTS.pixel_formats);
export const FourccOptionSchema = z.enum(CAMERA_DEFAULTS.fourcc_options);


// Helper function updated to use new enum values
export const createDefaultCameraConfig = (index: number, label: string) => ({
    camera_id: index,
    camera_name: label || `Camera ${index}`,
    use_this_camera: true,
    resolution: CAMERA_DEFAULTS.resolution.default,
    color_channels: 3,
    pixel_format: CAMERA_DEFAULTS.pixel_formats[0],
    exposure_mode: CAMERA_DEFAULTS.exposure_modes[0], // MANUAL
    exposure: CAMERA_DEFAULTS.exposure.default,
    framerate: CAMERA_DEFAULTS.framerate.default,
    rotation: CAMERA_DEFAULTS.rotation_options[0], // 'No Rotation'
    capture_fourcc: CAMERA_DEFAULTS.fourcc_options[0],
    writer_fourcc: CAMERA_DEFAULTS.fourcc_options[0], // 'X264'
    constraints: CAMERA_DEFAULTS
});

export const CameraConfigSchema = z.object({
    camera_id: z.number(),
    camera_name: z.string(),
    use_this_camera: z.boolean(),
    resolution: z.object({
        width: z.number().int(),
        height: z.number().int()
    }),
    color_channels: z.number(),
    pixel_format: PixelFormatSchema,
    exposure_mode: ExposureModeSchema,
    exposure: z.union([z.number(), z.literal('AUTO')]),
    framerate: z.number(),
    rotation: RotationOptionSchema,
    capture_fourcc: FourccOptionSchema,
    writer_fourcc: FourccOptionSchema,
});

export const CameraConfigsSchema = z.record(z.string(), CameraConfigSchema );


// Export the types
export type CameraConfig = z.infer<typeof CameraConfigSchema>;
export type CameraConfigs = z.infer<typeof CameraConfigsSchema>;
export type CameraDefaults = typeof CAMERA_DEFAULTS;
export type ResolutionPreset = z.infer<typeof ResolutionPresetSchema>;
export type ExposureMode = z.infer<typeof ExposureModeSchema>;
export type RotationOption = z.infer<typeof RotationOptionSchema>;
export type PixelFormat = z.infer<typeof PixelFormatSchema>;
export type FourccOption = z.infer<typeof FourccOptionSchema>;
