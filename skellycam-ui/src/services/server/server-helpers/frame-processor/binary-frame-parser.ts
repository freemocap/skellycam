// binary-frame-parser.ts
import { CameraConfig } from '@/store/slices/cameras';
import {
    MESSAGE_TYPE,
    CAMERA_CONFIG_FIELDS,
    CAMERA_CONFIG_SIZE,
    PAYLOAD_HEADER_FIELDS,
    PAYLOAD_HEADER_SIZE,
    FRAME_HEADER_FIELDS,
    FRAME_HEADER_SIZE,
    ROTATION_VALUES,
    PROTOCOL_LIMITS,
    type RotationOption,
} from './binary-protocol';

export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    bitmap: ImageBitmap;
    config: CameraConfig;
}

// Single reusable TextDecoder - created once, used forever
const sharedTextDecoder = new TextDecoder();

// Optimized ImageBitmap options for camera feeds
const BITMAP_OPTIONS: ImageBitmapOptions = {
    premultiplyAlpha: 'none',
    colorSpaceConversion: 'none',
    resizeQuality: 'pixelated'
};

/**
 * Parse a Unicode string field from the buffer
 * Handles numpy's UTF-32 encoding (4 bytes per character)
 */
function parseUnicodeField(view: DataView, baseOffset: number, fieldOffset: number, size: number): string {
    const offset = baseOffset + fieldOffset;

    // For numpy U128 fields, we need to handle UTF-32 encoding
    // Find the actual string length (until null terminator or max size)
    let actualLength = 0;
    for (let i = 0; i < size; i += 4) {
        const codePoint = view.getUint32(offset + i, true);
        if (codePoint === 0) break;
        actualLength += 4;
    }

    if (actualLength === 0) return '';

    // Extract the string data
    const codePoints: number[] = [];
    for (let i = 0; i < actualLength; i += 4) {
        codePoints.push(view.getUint32(offset + i, true));
    }

    // Convert code points to string
    return String.fromCodePoint(...codePoints);
}

/**
 * Parse an ASCII string field from the buffer
 */
function parseAsciiField(view: DataView, baseOffset: number, fieldOffset: number, size: number): string {
    const offset = baseOffset + fieldOffset;

    // Find actual string length (until null terminator)
    let length = 0;
    while (length < size && view.getUint8(offset + length) !== 0) {
        length++;
    }

    if (length === 0) return '';

    const bytes = new Uint8Array(view.buffer, view.byteOffset + offset, length);
    return sharedTextDecoder.decode(bytes);
}

/**
 * Parse a FOURCC code from 4 bytes
 */
function parseFourcc(view: DataView, baseOffset: number, fieldOffset: number): string {
    const offset = baseOffset + fieldOffset;
    let str = '';

    for (let i = 0; i < 4; i++) {
        const byte = view.getUint8(offset + i);
        if (byte !== 0) {
            str += String.fromCharCode(byte);
        }
    }

    return str || 'MJPG'; // Default to MJPG if empty
}

/**
 * Parse camera configuration from buffer using protocol offsets
 */
function parseCameraConfig(view: DataView, baseOffset: number): CameraConfig {
    // Parse each field using the predefined offsets
    const cameraId = parseUnicodeField(
        view,
        baseOffset,
        CAMERA_CONFIG_FIELDS.camera_id.offset,
        CAMERA_CONFIG_FIELDS.camera_id.size
    );

    const cameraIndex = view.getInt32(
        baseOffset + CAMERA_CONFIG_FIELDS.camera_index.offset,
        true
    );

    const cameraName = parseUnicodeField(
        view,
        baseOffset,
        CAMERA_CONFIG_FIELDS.camera_name.offset,
        CAMERA_CONFIG_FIELDS.camera_name.size
    );

    const useThisCamera = view.getUint8(
        baseOffset + CAMERA_CONFIG_FIELDS.use_this_camera.offset
    ) !== 0;

    const resolutionHeight = view.getInt32(
        baseOffset + CAMERA_CONFIG_FIELDS.resolution_height.offset,
        true
    );

    const resolutionWidth = view.getInt32(
        baseOffset + CAMERA_CONFIG_FIELDS.resolution_width.offset,
        true
    );

    const colorChannels = view.getInt32(
        baseOffset + CAMERA_CONFIG_FIELDS.color_channels.offset,
        true
    );

    const pixelFormat = parseAsciiField(
        view,
        baseOffset,
        CAMERA_CONFIG_FIELDS.pixel_format.offset,
        CAMERA_CONFIG_FIELDS.pixel_format.size
    ).trim() as 'RGB' | 'BGR' | 'GRAY';

    const exposureMode = parseAsciiField(
        view,
        baseOffset,
        CAMERA_CONFIG_FIELDS.exposure_mode.offset,
        CAMERA_CONFIG_FIELDS.exposure_mode.size
    ).trim() as 'MANUAL' | 'AUTO' | 'RECOMMEND';

    const exposure = view.getInt32(
        baseOffset + CAMERA_CONFIG_FIELDS.exposure.offset,
        true
    );

    const framerate = view.getFloat32(
        baseOffset + CAMERA_CONFIG_FIELDS.framerate.offset,
        true
    );

    const rotationValue = view.getInt32(
        baseOffset + CAMERA_CONFIG_FIELDS.rotation.offset,
        true
    );

    const rotation = (ROTATION_VALUES[rotationValue as keyof typeof ROTATION_VALUES] || 'None') as RotationOption;

    const captureFourcc = parseFourcc(
        view,
        baseOffset,
        CAMERA_CONFIG_FIELDS.capture_fourcc.offset
    ) as 'MJPG' | 'X264' | 'YUYV' | 'H264';

    const writerFourcc = parseFourcc(
        view,
        baseOffset,
        CAMERA_CONFIG_FIELDS.writer_fourcc.offset
    ) as 'MJPG' | 'X264' | 'YUYV' | 'H264';

    return {
        camera_id: cameraId,
        camera_index: cameraIndex,
        camera_name: cameraName,
        use_this_camera: useThisCamera,
        resolution: {
            width: resolutionWidth,
            height: resolutionHeight
        },
        framerate: framerate,
        color_channels: colorChannels,
        pixel_format: pixelFormat,
        rotation: rotation,
        exposure_mode: exposureMode,
        exposure: exposure,
        capture_fourcc: captureFourcc,
        writer_fourcc: writerFourcc,
    };
}

/**
 * Parse a multi-frame payload from binary data
 */
export async function parseMultiFramePayload(
    data: ArrayBuffer
): Promise<ParsedFrame[] | null> {
    const view = new DataView(data);

    // Validate payload header
    const messageType = view.getUint8(PAYLOAD_HEADER_FIELDS.message_type.offset);
    if (messageType !== MESSAGE_TYPE.PAYLOAD_HEADER) {
        console.warn(`Invalid payload header: expected ${MESSAGE_TYPE.PAYLOAD_HEADER}, got ${messageType}`);
        return null;
    }

    // Extract payload header fields
    const frameNumber = Number(
        view.getBigInt64(PAYLOAD_HEADER_FIELDS.frame_number.offset, true)
    );

    const numCameras = view.getInt32(
        PAYLOAD_HEADER_FIELDS.number_of_cameras.offset,
        true
    );

    // Validate camera count
    if (numCameras <= 0 || numCameras > PROTOCOL_LIMITS.MAX_CAMERAS) {
        console.warn(`Invalid camera count: ${numCameras}`);
        return null;
    }

    // Pre-allocate array for frame metadata
    const frameMetadata: Array<{
        cameraId: string;
        cameraIndex: number;
        frameNumber: number;
        width: number;
        height: number;
        config: CameraConfig;
        jpegStart: number;
        jpegLength: number;
    }> = new Array(numCameras);

    let currentOffset = PAYLOAD_HEADER_SIZE;
    let validFrameCount = 0;

    // Parse each frame header
    for (let i = 0; i < numCameras; i++) {
        // Validate frame header message type
        const frameMessageType = view.getUint8(
            currentOffset + FRAME_HEADER_FIELDS.message_type.offset
        );

        if (frameMessageType !== MESSAGE_TYPE.FRAME_METADATA) {
            console.warn(`Invalid frame header at offset ${currentOffset}: expected ${MESSAGE_TYPE.FRAME_METADATA}, got ${frameMessageType}`);
            break;
        }

        // Extract frame number
        const frameNum = Number(
            view.getBigInt64(
                currentOffset + FRAME_HEADER_FIELDS.frame_number.offset,
                true
            )
        );

        // Parse camera config
        const config = parseCameraConfig(
            view,
            currentOffset + FRAME_HEADER_FIELDS.camera_config.offset
        );

        // Extract image metadata
        const width = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.image_width.offset,
            true
        );

        const height = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.image_height.offset,
            true
        );

        const jpegLength = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.jpeg_string_length.offset,
            true
        );

        // Validate JPEG length
        if (jpegLength <= 0 || jpegLength > PROTOCOL_LIMITS.MAX_FRAME_SIZE) {
            console.warn(`Invalid JPEG length: ${jpegLength}`);
            break;
        }

        // Store metadata
        frameMetadata[validFrameCount] = {
            cameraId: config.camera_id,
            cameraIndex: config.camera_index,
            frameNumber: frameNum,
            width: width,
            height: height,
            config: config,
            jpegStart: currentOffset + FRAME_HEADER_SIZE,
            jpegLength: jpegLength
        };

        validFrameCount++;
        currentOffset += FRAME_HEADER_SIZE + jpegLength;
    }

    if (validFrameCount === 0) {
        console.warn('No valid frames found in payload');
        return null;
    }

    // Trim array to actual size
    frameMetadata.length = validFrameCount;

    // Create ImageBitmaps in parallel
    const bitmapPromises = frameMetadata.map(async (metadata) => {
        try {
            const jpegData = new Uint8Array(data, metadata.jpegStart, metadata.jpegLength);
            const blob = new Blob([jpegData], { type: 'image/jpeg' });
            const bitmap = await createImageBitmap(blob, BITMAP_OPTIONS);

            return {
                cameraId: metadata.cameraId,
                cameraIndex: metadata.cameraIndex,
                frameNumber: metadata.frameNumber,
                width: metadata.width,
                height: metadata.height,
                bitmap: bitmap,
                config: metadata.config
            } as ParsedFrame;
        } catch (error) {
            console.error(`Failed to create bitmap for camera ${metadata.cameraId}:`, error);
            throw error;
        }
    });

    return Promise.all(bitmapPromises);
}
