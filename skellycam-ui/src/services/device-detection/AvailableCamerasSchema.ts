import {z} from "zod";

// Schema for CameraDeviceInfo
const CameraDeviceInfoSchema = z.object({
    description: z.string(),
    device_address: z.string(),
    cv2_port: z.number(),
    available_video_formats: z.array(
        z.object({
            width: z.number(),
            height: z.number(),
            pixel_format: z.string(),
            framerate: z.number(),
        })
    ),
});

// Schema for AvailableCameras, a dictionary of CameraDeviceInfo
export const AvailableCamerasSchema = z.record(z.string(), CameraDeviceInfoSchema);
