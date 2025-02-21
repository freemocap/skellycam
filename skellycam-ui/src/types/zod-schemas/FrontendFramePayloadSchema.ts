import { z } from "zod";

// Define the schema for JPEG images with base64 strings
export const JpegImagesSchema = z.record(
    z.string(), // The keys are strings
    z.string()//.regex(/^data:image\/jpeg;base64,/, "Invalid base64 JPEG string") // The values are base64 JPEG strings
);



// Update the FrontendFramePayloadSchema to use the defined schemas
export const FrontendFramePayloadSchema = z.object({
    type: z.literal('FrontendFramePayload'),
    jpeg_images: JpegImagesSchema, // Use the JpegImagesSchema
    camera_configs: z.record(z.any()), // Allow any shape for camera_configs
    multi_frame_metadata: z.any(), // Allow any value for multi_frame_metadata
    utc_ns_to_perf_ns: z.any(), // Allow any value for utc_ns_to_perf_ns
    multi_frame_number: z.number().int().default(0),
});


