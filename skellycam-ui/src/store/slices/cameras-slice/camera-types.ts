import { z } from "zod";

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

export const CameraConfigsSchema = z.record(z.number(), CameraConfigSchema );

const CameraDeviceInfoSchema = z.object({
    name: z.string(),
    cv2_port: z.number(),
    status: z.enum(['available', 'unavailable']),
    device_type: z.enum(['camera', 'screen', 'virtual_camera', 'unknown']),
});

export const DetectedDevicesSchema = z.record(z.string(), CameraDeviceInfoSchema);


// Export the types
export type CameraDeviceInfo = z.infer<typeof CameraDeviceInfoSchema>;
export type DetectedCameras = z.infer<typeof DetectedDevicesSchema>;
export type CameraConfig = z.infer<typeof CameraConfigSchema>;
export type CameraConfigs = z.infer<typeof CameraConfigsSchema>;
