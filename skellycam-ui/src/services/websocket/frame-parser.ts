
const PROTOCOL_SIZES = {
    PAYLOAD_HEADER: 24,
    FRAME_HEADER: 56,
} as const;

const MESSAGE_TYPE = {
    PAYLOAD_HEADER: 0,
    FRAME_HEADER: 1,
} as const;

export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    bitmap: ImageBitmap;
}

// Single reusable TextDecoder - created once, used forever
const sharedTextDecoder = new TextDecoder();

// Optimized ImageBitmap options for camera feeds
const BITMAP_OPTIONS: ImageBitmapOptions = {
    premultiplyAlpha: 'none',     // No alpha processing needed for camera feeds
    colorSpaceConversion: 'none',  // Skip color space conversion
    resizeQuality: 'pixelated'     // Fastest resize algorithm
};

export async function parseMultiFramePayload(
    data: ArrayBuffer
): Promise<ParsedFrame[] | null> {
    const view = new DataView(data);

    // Quick validation
    if (view.getUint8(0) !== MESSAGE_TYPE.PAYLOAD_HEADER) {
        return null;
    }

    const numCameras = view.getInt32(16, true);
    if (numCameras <= 0 || numCameras > 100) {
        return null;
    }

    // Pre-allocate array with exact size to avoid dynamic resizing
    const frameMetadata: Array<{
        cameraId: string;
        cameraIndex: number;
        frameNumber: number;
        width: number;
        height: number;
        jpegStart: number;
        jpegLength: number;
    }> = new Array(numCameras);

    let offset = PROTOCOL_SIZES.PAYLOAD_HEADER;
    let validFrameCount = 0;

    // First pass: Extract all metadata (fast, synchronous)
    for (let i = 0; i < numCameras; i++) {
        // Validate frame header
        if (view.getUint8(offset) !== MESSAGE_TYPE.FRAME_HEADER) {
            break;
        }

        // Extract frame number
        const frameNumber = Number(view.getBigInt64(offset + 8, true));

        // Extract camera ID efficiently
        // Instead of creating intermediate Uint8Array, read directly from DataView
        const cameraIdOffset = offset + 16;
        let idLength = 0;

        // Find null terminator or max length
        while (idLength < 16 && view.getUint8(cameraIdOffset + idLength) !== 0) {
            idLength++;
        }

        // Decode camera ID using a view (no copy)
        const cameraIdBytes = new Uint8Array(data, cameraIdOffset, idLength);
        const cameraId = sharedTextDecoder.decode(cameraIdBytes);

        // Extract remaining metadata
        const cameraIndex = view.getInt32(offset + 32, true);
        const width = view.getInt32(offset + 36, true);
        const height = view.getInt32(offset + 40, true);
        const jpegLength = view.getInt32(offset + 48, true);

        // Store metadata and JPEG location (not the data itself yet)
        frameMetadata[validFrameCount] = {
            cameraId,
            cameraIndex,
            frameNumber,
            width,
            height,
            jpegStart: offset + PROTOCOL_SIZES.FRAME_HEADER,
            jpegLength
        };

        validFrameCount++;
        offset += PROTOCOL_SIZES.FRAME_HEADER + jpegLength;
    }

    if (validFrameCount === 0) {
        return null;
    }

    // Trim array to actual size
    frameMetadata.length = validFrameCount;

    // Second pass: Create all ImageBitmaps in parallel (the slow part)
    // This is where we get the big performance win
    const bitmapPromises = frameMetadata.map(async (metadata) => {
        // Create a view into the existing ArrayBuffer (no copy)
        const jpegData = new Uint8Array(data, metadata.jpegStart, metadata.jpegLength);

        // Create blob (unavoidable - needed for createImageBitmap)
        const blob = new Blob([jpegData], { type: 'image/jpeg' });

        // Create bitmap with optimized settings
        // This happens in parallel for all frames
        const bitmap = await createImageBitmap(blob, BITMAP_OPTIONS);

        // Return complete frame
        return {
            cameraId: metadata.cameraId,
            cameraIndex: metadata.cameraIndex,
            frameNumber: metadata.frameNumber,
            width: metadata.width,
            height: metadata.height,
            bitmap
        } as ParsedFrame;
    });

    // Wait for all bitmaps to complete
    // The browser can decode these in parallel using multiple threads internally
    return Promise.all(bitmapPromises);
}
