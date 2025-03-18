import {z} from "zod";
import {AvailableCamerasSchema} from "@/services/device-detection/AvailableCamerasSchema";

export const CurrentFrameRateSchema = z.object({
    mean_frame_duration_ms: z.number(),
    mean_frames_per_second: z.number(),
    recent_frames_per_second: z.number(),
    recent_mean_frame_duration_ms: z.number(),
});

export const CameraConfigSchema = z.object({
    camera_id: z.number(),
    camera_name: z.string(),
    use_this_camera: z.boolean(),
    resolution: z.object({
        width: z.number(),
        height: z.number(),
    }),
    color_channels: z.number(),
    pixel_format: z.string(),
    exposure_mode: z.string(),
    exposure: z.union([z.number(), z.string()]),
    framerate: z.number(),
    rotation: z.string(),
    capture_fourcc: z.string(),
    writer_fourcc: z.string(),
});


export const SkellyCamAppStateSchema = z.object({
    type: z.literal("SkellycamAppStateDTO"),
    state_timestamp: z.string().optional(), // Assuming a string timestamp
    camera_configs: z.record(z.string(), CameraConfigSchema).optional(), // Optional CameraConfigs
    available_devices: AvailableCamerasSchema.optional(), // Optional AvailableCameras
    current_framerate: CurrentFrameRateSchema.nullable().optional(), // Allow null or undefined
    is_recording_flag: z.boolean(),
    record_directory: z.string().optional(),
});
