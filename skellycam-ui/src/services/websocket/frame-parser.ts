
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

export async function parseFramePayload(
    data: ArrayBuffer,
    textDecoder: TextDecoder
): Promise<ParsedFrame[] | null> {
    const view = new DataView(data);

    // Check message type
    if (view.getUint8(0) !== MESSAGE_TYPE.PAYLOAD_HEADER) return null;

    const numCameras = view.getInt32(16, true);
    if (numCameras <= 0 || numCameras > 100) return null;

    let offset = PROTOCOL_SIZES.PAYLOAD_HEADER;
    const frames: ParsedFrame[] = [];

    for (let i = 0; i < numCameras; i++) {
        // Check frame header
        if (view.getUint8(offset) !== MESSAGE_TYPE.FRAME_HEADER) break;

        const frameNumber = Number(view.getBigInt64(offset + 8, true));

        // Extract camera ID
        const cameraIdBytes = new Uint8Array(data, offset + 16, 16);
        let idLength = 0;
        while (idLength < 16 && cameraIdBytes[idLength] !== 0) idLength++;
        const cameraId = textDecoder.decode(cameraIdBytes.subarray(0, idLength));

        const cameraIndex = view.getInt32(offset + 32, true);
        const width = view.getInt32(offset + 36, true);
        const height = view.getInt32(offset + 40, true);
        const jpegLength = view.getInt32(offset + 48, true);

        offset += PROTOCOL_SIZES.FRAME_HEADER;

        const jpegData = new Uint8Array(data, offset, jpegLength);
        offset += jpegLength;

        frames.push({
            cameraId,
            cameraIndex,
            frameNumber,
            width,
            height,
            bitmap: await createImageBitmap(new Blob([jpegData], { type: 'image/jpeg' }))
        });
    }

    return frames.length > 0 ? frames : null;
}
