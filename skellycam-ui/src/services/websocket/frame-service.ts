// ============================================
// OPTIMIZED BINARY FRAME PROCESSOR
// ============================================

// Constants matching Python protocol
const PROTOCOL_SIZES = {
    PAYLOAD_HEADER: 24,
    FRAME_HEADER: 56,
    PAYLOAD_FOOTER: 24,
} as const;

const MESSAGE_TYPE = {
    PAYLOAD_HEADER: 0,
    FRAME_HEADER: 1,
    PAYLOAD_FOOTER: 2,
} as const;

interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    bitmap: ImageBitmap;
}



type FrameHandler = (parsedFrame: ParsedFrame) => void;

// ============================================
// UNIFIED FRAME PROCESSING SERVICE
// ============================================

class FrameService {
    private static instance: FrameService;

    // Frame processing
    private handlers = new Map<string, Set<FrameHandler>>();

    // Buffers for parsing (reuse to avoid allocations)
    private textDecoder = new TextDecoder();

    // Performance settings
    private readonly MAX_RECONNECT_ATTEMPTS = 10;

    // Debug mode (set to false in production)
    private readonly DEBUG = false;

    private constructor() {
    }

    static getInstance(): FrameService {
        if (!FrameService.instance) {
            FrameService.instance = new FrameService();
        }
        return FrameService.instance;
    }

    // ============================================
    // PUBLIC API
    // ============================================



    subscribe(cameraId: string, handler: FrameHandler): () => void {
        if (!this.handlers.has(cameraId)) {
            this.handlers.set(cameraId, new Set());
        }
        this.handlers.get(cameraId)!.add(handler);

        // Return unsubscribe function
        return () => {
            const handlers = this.handlers.get(cameraId);
            if (handlers) {
                handlers.delete(handler);
                if (handlers.size === 0) {
                    this.handlers.delete(cameraId);
                }
            }
        };
    }



    // ============================================
    // BINARY PARSING
    // ============================================

    private processBinaryFrame(data: ArrayBuffer): void {
        const view = new DataView(data);
        let offset = 0;

        // Quick validation - check message type
        if (view.getUint8(0) !== MESSAGE_TYPE.PAYLOAD_HEADER) return;

        // Parse payload header
        const frameNumber = Number(view.getBigInt64(8, true));
        const numCameras = view.getInt32(16, true);

        if (numCameras <= 0 || numCameras > 100) return;

        offset += PROTOCOL_SIZES.PAYLOAD_HEADER;

        // Process each camera frame
        const bitmapPromises: Promise<void>[] = [];

        for (let i = 0; i < numCameras; i++) {
            const frameData = this.parseFrame(data, view, offset);
            if (!frameData) break;

            offset = frameData.nextOffset;

            // Get handlers for this camera
            const handlers = this.handlers.get(frameData.frame.cameraId);
            if (!handlers || handlers.size === 0) continue;

            // Create bitmap and notify handlers
            const promise = this.createAndDispatchBitmap(frameData.frame, handlers);
            bitmapPromises.push(promise);
        }

        if (bitmapPromises.length > 0) {
            // Process all bitmaps in parallel
            Promise.all(bitmapPromises);
        }
    }

    private parseFrame(
        data: ArrayBuffer,
        view: DataView,
        offset: number
    ): { frame: ParsedFrame; nextOffset: number } | null {
        // Quick validation
        if (view.getUint8(offset) !== MESSAGE_TYPE.FRAME_HEADER) return null;

        const frameNumber = Number(view.getBigInt64(offset + 8, true));

        // Extract camera ID efficiently
        const cameraIdBytes = new Uint8Array(data, offset + 16, 16);
        let idLength = 0;
        while (idLength < 16 && cameraIdBytes[idLength] !== 0) idLength++;
        const cameraId = this.textDecoder.decode(cameraIdBytes.subarray(0, idLength));

        const cameraIndex = view.getInt32(offset + 32, true);
        const width = view.getInt32(offset + 36, true);
        const height = view.getInt32(offset + 40, true);
        const jpegLength = view.getInt32(offset + 48, true);

        offset += PROTOCOL_SIZES.FRAME_HEADER;

        // Create view of JPEG data (no copy)
        const jpegData = new Uint8Array(data, offset, jpegLength);

        return {
            frame: {
                cameraId,
                cameraIndex,
                frameNumber,
                width,
                height,
                await createImageBitmap(new Blob([jpegData], {type: 'image/jpeg'}))
            },
            nextOffset: offset + jpegLength
        };
    }

    private async createAndDispatchBitmap(
        frame: ParsedFrame,
        handlers: Set<FrameHandler>
    ): Promise<void> {
        try {
            // Dispatch to all handlers
            handlers.forEach(handler => {
                try {
                    handler(frame);
                } catch (error) {
                    // Silent fail in production
                    if (this.DEBUG) console.error('Handler error:', error);
                }
            });

        } catch (error) {
            if (this.DEBUG) console.error('Bitmap creation error:', error);
        }
    }

}
