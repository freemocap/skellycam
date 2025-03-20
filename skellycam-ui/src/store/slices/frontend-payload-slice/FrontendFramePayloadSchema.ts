import {z} from "zod";
import {CameraConfigsSchema} from "@/store/slices/cameras-slice/camerasSlice";
import {CurrentFramerateSchema} from "@/store/slices/framerateSlice";

export const JpegImagesSchema = z.record(
    z.string(),
    z.string()
);

export const FrontendFramePayloadSchema = z.object({
    jpeg_images: JpegImagesSchema,
    camera_configs: CameraConfigsSchema,
    multi_frame_metadata: z.record(z.string(), z.unknown()),
    utc_ns_to_perf_ns: z.record(z.string(), z.number()),
    multi_frame_number: z.number().int(),
    backend_framerate: CurrentFramerateSchema.nullable(),
    frontend_framerate: CurrentFramerateSchema.nullable(),
});

export type JpegImages = z.infer<typeof JpegImagesSchema>;
export type FrontendFramePayload = z.infer<typeof FrontendFramePayloadSchema>;
