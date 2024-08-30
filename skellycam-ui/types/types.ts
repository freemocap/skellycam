type CameraId = string;

export interface FrontendImagePayload {
    jpeg_images: Record<CameraId, Uint8Array | null>;
    utc_ns_to_perf_ns: Record<string, number>;
    multi_frame_number: number;
}
