// ============================================
// BINARY FRAME PARSER (binary-frame-parser.ts)
// ============================================
// Handles parsing of binary WebSocket frame data according to Python protocol

// Message types from Python protocol
export enum MessageType {
    PAYLOAD_HEADER = 0,
    FRAME_HEADER = 1,
    PAYLOAD_FOOTER = 2,
}

// Binary protocol constants - matching Python dtype definitions
export const PROTOCOL_SIZES = {
    PAYLOAD_HEADER: 24,
    FRAME_HEADER: 56,
    PAYLOAD_FOOTER: 24,
} as const;

// Payload Header layout
const PAYLOAD_HEADER_LAYOUT = {
    MESSAGE_TYPE: { offset: 0, size: 1 },
    PADDING: { offset: 1, size: 7 },
    FRAME_NUMBER: { offset: 8, size: 8 },
    NUM_CAMERAS: { offset: 16, size: 4 },
    PADDING_END: { offset: 20, size: 4 },
} as const;

// Frame Header layout
const FRAME_HEADER_LAYOUT = {
    MESSAGE_TYPE: { offset: 0, size: 1 },
    PADDING: { offset: 1, size: 7 },
    FRAME_NUMBER: { offset: 8, size: 8 },
    CAMERA_ID: { offset: 16, size: 16 },
    CAMERA_INDEX: { offset: 32, size: 4 },
    IMAGE_WIDTH: { offset: 36, size: 4 },
    IMAGE_HEIGHT: { offset: 40, size: 4 },
    COLOR_CHANNELS: { offset: 44, size: 4 },
    JPEG_LENGTH: { offset: 48, size: 4 },
    PADDING_END: { offset: 52, size: 4 },
} as const;

// Payload Footer layout (same structure as header)
const PAYLOAD_FOOTER_LAYOUT = {
    MESSAGE_TYPE: { offset: 0, size: 1 },
    PADDING: { offset: 1, size: 7 },
    FRAME_NUMBER: { offset: 8, size: 8 },
    NUM_CAMERAS: { offset: 16, size: 4 },
    PADDING_END: { offset: 20, size: 4 },
} as const;

// Type definitions
export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    jpegData: Uint8Array;
}

export interface ParsedPayload {
    frameNumber: number;
    frames: ParsedFrame[];
}

interface PayloadHeader {
    messageType: number;
    frameNumber: number;
    numCameras: number;
}

interface FrameHeader {
    messageType: number;
    frameNumber: number;
    cameraId: string;
    cameraIndex: number;
    width: number;
    height: number;
    colorChannels: number;
    jpegLength: number;
}

/**
 * Binary frame parser for multicamera streaming protocol
 */
export class BinaryFrameParser {
    private textDecoder = new TextDecoder();
    private tempCameraIdBuffer = new Uint8Array(16);

    // Performance monitoring
    private parseWarningsEnabled = true;
    private maxParseTimeMs = 5; // Warn if parsing takes more than 5ms

    constructor(options?: {
        parseWarningsEnabled?: boolean;
        maxParseTimeMs?: number;
    }) {
        if (options?.parseWarningsEnabled !== undefined) {
            this.parseWarningsEnabled = options.parseWarningsEnabled;
        }
        if (options?.maxParseTimeMs !== undefined) {
            this.maxParseTimeMs = options.maxParseTimeMs;
        }
    }

    /**
     * Parse binary frame data from WebSocket
     */
    parseFrameData(data: ArrayBuffer): ParsedPayload | null {
        const startTime = this.parseWarningsEnabled ? performance.now() : 0;

        try {
            const result = this.parsePayload(data);

            if (this.parseWarningsEnabled) {
                const parseTime = performance.now() - startTime;
                if (parseTime > this.maxParseTimeMs) {
                    console.warn(`Binary parsing took ${parseTime.toFixed(2)}ms (threshold: ${this.maxParseTimeMs}ms)`);
                }
            }

            return result;
        } catch (error) {
            console.error('Failed to parse binary frame data:', error);
            return null;
        }
    }

    private parsePayload(data: ArrayBuffer): ParsedPayload | null {
        const dataView = new DataView(data);
        let offset = 0;

        // Parse Payload Header
        const header = this.parsePayloadHeader(dataView, offset);
        if (!header) return null;

        offset += PROTOCOL_SIZES.PAYLOAD_HEADER;

        // Parse all camera frames
        const frames: ParsedFrame[] = [];
        for (let i = 0; i < header.numCameras; i++) {
            const frame = this.parseFrame(
                data,
                dataView,
                offset,
                header.frameNumber
            );

            if (!frame) return null;

            frames.push(frame.parsedFrame);
            offset = frame.nextOffset;
        }

        // Verify Payload Footer
        if (!this.verifyPayloadFooter(dataView, offset, header)) {
            return null;
        }

        return {
            frameNumber: header.frameNumber,
            frames,
        };
    }

    private parsePayloadHeader(dataView: DataView, offset: number): PayloadHeader | null {
        // Check buffer bounds
        if (dataView.byteLength < offset + PROTOCOL_SIZES.PAYLOAD_HEADER) {
            console.error('Buffer too small for payload header');
            return null;
        }

        const messageType = dataView.getUint8(offset + PAYLOAD_HEADER_LAYOUT.MESSAGE_TYPE.offset);
        if (messageType !== MessageType.PAYLOAD_HEADER) {
            console.error(`Expected payload header (${MessageType.PAYLOAD_HEADER}), got ${messageType}`);
            return null;
        }

        const frameNumber = Number(dataView.getBigInt64(
            offset + PAYLOAD_HEADER_LAYOUT.FRAME_NUMBER.offset,
            true // little-endian
        ));

        const numCameras = dataView.getInt32(
            offset + PAYLOAD_HEADER_LAYOUT.NUM_CAMERAS.offset,
            true
        );

        if (numCameras <= 0 || numCameras > 100) { // Sanity check
            console.error(`Invalid number of cameras: ${numCameras}`);
            return null;
        }

        return { messageType, frameNumber, numCameras };
    }

    private parseFrame(
        data: ArrayBuffer,
        dataView: DataView,
        offset: number,
        expectedFrameNumber: number
    ): { parsedFrame: ParsedFrame; nextOffset: number } | null {
        // Parse Frame Header
        const frameHeader = this.parseFrameHeader(dataView, offset);
        if (!frameHeader) return null;

        // Verify frame number matches
        if (frameHeader.frameNumber !== expectedFrameNumber) {
            console.error(
                `Frame number mismatch: expected ${expectedFrameNumber}, got ${frameHeader.frameNumber}`
            );
            return null;
        }

        offset += PROTOCOL_SIZES.FRAME_HEADER;

        // Check JPEG data bounds
        if (offset + frameHeader.jpegLength > dataView.byteLength) {
            console.error('Buffer too small for JPEG data');
            return null;
        }

        // Extract JPEG data (create a view, not a copy, for efficiency)
        const jpegData = new Uint8Array(data, offset, frameHeader.jpegLength);
        offset += frameHeader.jpegLength;

        return {
            parsedFrame: {
                cameraId: frameHeader.cameraId,
                cameraIndex: frameHeader.cameraIndex,
                frameNumber: frameHeader.frameNumber,
                width: frameHeader.width,
                height: frameHeader.height,
                jpegData,
            },
            nextOffset: offset,
        };
    }

    private parseFrameHeader(dataView: DataView, offset: number): FrameHeader | null {
        // Check buffer bounds
        if (dataView.byteLength < offset + PROTOCOL_SIZES.FRAME_HEADER) {
            console.error('Buffer too small for frame header');
            return null;
        }

        const messageType = dataView.getUint8(offset + FRAME_HEADER_LAYOUT.MESSAGE_TYPE.offset);
        if (messageType !== MessageType.FRAME_HEADER) {
            console.error(`Expected frame header (${MessageType.FRAME_HEADER}), got ${messageType}`);
            return null;
        }

        const frameNumber = Number(dataView.getBigInt64(
            offset + FRAME_HEADER_LAYOUT.FRAME_NUMBER.offset,
            true
        ));

        // Extract camera ID efficiently
        const cameraId = this.extractCameraId(dataView, offset + FRAME_HEADER_LAYOUT.CAMERA_ID.offset);

        const cameraIndex = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.CAMERA_INDEX.offset,
            true
        );

        const width = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.IMAGE_WIDTH.offset,
            true
        );

        const height = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.IMAGE_HEIGHT.offset,
            true
        );

        const colorChannels = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.COLOR_CHANNELS.offset,
            true
        );

        const jpegLength = dataView.getInt32(
            offset + FRAME_HEADER_LAYOUT.JPEG_LENGTH.offset,
            true
        );

        // Sanity checks
        if (width <= 0 || width > 10000 || height <= 0 || height > 10000) {
            console.error(`Invalid image dimensions: ${width}x${height}`);
            return null;
        }

        if (jpegLength <= 0 || jpegLength > 10 * 1024 * 1024) { // Max 10MB per frame
            console.error(`Invalid JPEG length: ${jpegLength}`);
            return null;
        }

        return {
            messageType,
            frameNumber,
            cameraId,
            cameraIndex,
            width,
            height,
            colorChannels,
            jpegLength,
        };
    }

    private extractCameraId(dataView: DataView, offset: number): string {
        // Create a view of the camera ID bytes
        const cameraIdBytes = new Uint8Array(
            dataView.buffer,
            dataView.byteOffset + offset,
            FRAME_HEADER_LAYOUT.CAMERA_ID.size
        );

        // Find null terminator
        let cameraIdLength = 0;
        while (
            cameraIdLength < FRAME_HEADER_LAYOUT.CAMERA_ID.size &&
            cameraIdBytes[cameraIdLength] !== 0
            ) {
            cameraIdLength++;
        }

        // Decode the string
        return this.textDecoder.decode(
            cameraIdBytes.subarray(0, cameraIdLength)
        );
    }

    private verifyPayloadFooter(
        dataView: DataView,
        offset: number,
        header: PayloadHeader
    ): boolean {
        // Check buffer bounds
        if (dataView.byteLength < offset + PROTOCOL_SIZES.PAYLOAD_FOOTER) {
            console.error('Buffer too small for payload footer');
            return false;
        }

        const footerMessageType = dataView.getUint8(
            offset + PAYLOAD_FOOTER_LAYOUT.MESSAGE_TYPE.offset
        );

        if (footerMessageType !== MessageType.PAYLOAD_FOOTER) {
            console.error(
                `Expected payload footer (${MessageType.PAYLOAD_FOOTER}), got ${footerMessageType}`
            );
            return false;
        }

        const footerFrameNumber = Number(dataView.getBigInt64(
            offset + PAYLOAD_FOOTER_LAYOUT.FRAME_NUMBER.offset,
            true
        ));

        const footerNumCameras = dataView.getInt32(
            offset + PAYLOAD_FOOTER_LAYOUT.NUM_CAMERAS.offset,
            true
        );

        if (footerFrameNumber !== header.frameNumber || footerNumCameras !== header.numCameras) {
            console.error(
                `Footer mismatch: expected ${header.frameNumber}/${header.numCameras}, ` +
                `got ${footerFrameNumber}/${footerNumCameras}`
            );
            return false;
        }

        return true;
    }

    /**
     * Get protocol information for debugging
     */
    getProtocolInfo() {
        return {
            sizes: PROTOCOL_SIZES,
            layouts: {
                payloadHeader: PAYLOAD_HEADER_LAYOUT,
                frameHeader: FRAME_HEADER_LAYOUT,
                payloadFooter: PAYLOAD_FOOTER_LAYOUT,
            },
            messageTypes: MessageType,
        };
    }
}
