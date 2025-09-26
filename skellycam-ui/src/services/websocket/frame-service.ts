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

export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    bitmap: ImageBitmap;
}


export type FrameHandler = (parsedFrame: ParsedFrame) => void;

// ============================================
// UNIFIED FRAME PROCESSING SERVICE
// ============================================

export class FrameService {
    private static instance: FrameService;

    // Frame processing
    private handlers = new Map<string, Set<FrameHandler>>();

    // Bitmap management
    private activeBitmaps = new Map<string, ImageBitmap>();

    // Buffers for parsing (reuse to avoid allocations)
    private textDecoder = new TextDecoder();

    // Performance settings
    private readonly MAX_FRAMES_IN_FLIGHT = 2; // Max concurrent frames per camera
    private readonly PERFORMANCE_SAMPLE_SIZE = 30; // Number of samples for averaging
    private readonly FRAME_DROP_THRESHOLD = 16; // Drop frames if behind by more than 16ms (60fps)

    // Debug mode (set to false in production)
    private readonly DEBUG = true;

    private constructor() {
        // Singleton constructor
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
                    // Cleanup when no more handlers
                    this.cleanupCameraResources(cameraId);
                }
            }
        };
    }


    // Public method to process incoming binary data
    async processBinaryFrame(data: ArrayBuffer): Promise<void> {
        await this.parseBinaryPayload(data);
    }

    // ============================================
    // BINARY PARSING
    // ============================================

    private async parseBinaryPayload(data: ArrayBuffer): Promise<void> {
        const view = new DataView(data);
        let offset = 0;

        // Quick validation - check message type
        if (view.getUint8(0) !== MESSAGE_TYPE.PAYLOAD_HEADER) return;

        // Parse payload header
        const frameNumber = Number(view.getBigInt64(8, true));
        const numCameras = view.getInt32(16, true);

        if (numCameras <= 0 || numCameras > 100) return;

        offset += PROTOCOL_SIZES.PAYLOAD_HEADER;

        // Track camera IDs in this payload
        const currentPayloadCameraIds = new Set<string>();

        // Process each camera frame
        const bitmapPromises: Promise<void>[] = [];

        for (let i = 0; i < numCameras; i++) {
            const frameData = this.parseFrameHeader(data, view, offset);
            if (!frameData) break;

            offset = frameData.nextOffset;

            // Track this camera as active
            currentPayloadCameraIds.add(frameData.cameraId);

            // Get handlers for this camera
            const handlers = this.handlers.get(frameData.cameraId);
            if (!handlers || handlers.size === 0) continue;


            // Create bitmap and notify handlers
            const promise = this.createAndDispatchBitmap(
                frameData,
                handlers
            );
            bitmapPromises.push(promise);
        }

        // Clean up cameras that are no longer in the payload
        for (const [cameraId, bitmap] of this.activeBitmaps) {
            if (!currentPayloadCameraIds.has(cameraId)) {
                try {
                    bitmap.close();
                } catch (e) {
                    // Bitmap might already be closed
                }
                this.activeBitmaps.delete(cameraId);
            }
        }

        if (bitmapPromises.length > 0) {
            // Process all bitmaps in parallel
            await Promise.all(bitmapPromises);
        }
    }

    private parseFrameHeader(
        data: ArrayBuffer,
        view: DataView,
        offset: number
    ): {
        cameraId: string;
        cameraIndex: number;
        frameNumber: number;
        width: number;
        height: number;
        jpegData: Uint8Array;
        nextOffset: number;
    } | null {
        // Quick validation
        if (view.getUint8(offset) !== MESSAGE_TYPE.FRAME_HEADER) return null;

        const frameNumber = Number(view.getBigInt64(offset + 8, true));

        // Extract camera ID efficiently
        const cameraIdBytes = new Uint8Array(data, offset + 16, 16);
        let idLength = 0;
        while (idLength < 16 && cameraIdBytes[idLength] !== 0) idLength++;
        const cameraId = this.textDecoder.decode(
            cameraIdBytes.subarray(0, idLength)
        );

        const cameraIndex = view.getInt32(offset + 32, true);
        const width = view.getInt32(offset + 36, true);
        const height = view.getInt32(offset + 40, true);
        const jpegLength = view.getInt32(offset + 48, true);

        offset += PROTOCOL_SIZES.FRAME_HEADER;

        // Create view of JPEG data (no copy)
        const jpegData = new Uint8Array(data, offset, jpegLength);

        return {
            cameraId,
            cameraIndex,
            frameNumber,
            width,
            height,
            jpegData,
            nextOffset: offset + jpegLength,
        };
    }



    private async createAndDispatchBitmap(
        frameData: {
            cameraId: string;
            cameraIndex: number;
            frameNumber: number;
            width: number;
            height: number;
            jpegData: Uint8Array;
        },
        handlers: Set<FrameHandler>
    ): Promise<void> {
        const startTime = performance.now();

        try {
            // Create ImageBitmap from JPEG data
            const blob = new Blob([frameData.jpegData], { type: 'image/jpeg' });
            const bitmap = await createImageBitmap(blob);

            const bitmapCreationTime = performance.now() - startTime;

            // Clean up old bitmap for this camera if it exists
            const oldBitmap = this.activeBitmaps.get(frameData.cameraId);
            if (oldBitmap) {
                try {
                    oldBitmap.close();
                } catch (e) {
                    // Bitmap might already be closed
                }
            }

            // Store new active bitmap
            this.activeBitmaps.set(frameData.cameraId, bitmap);

            // Create ParsedFrame with the bitmap
            const parsedFrame: ParsedFrame = {
                cameraId: frameData.cameraId,
                cameraIndex: frameData.cameraIndex,
                frameNumber: frameData.frameNumber,
                width: frameData.width,
                height: frameData.height,
                bitmap,
            };

            // Dispatch to all handlers
            handlers.forEach(handler => {
                try {
                    handler(parsedFrame);
                } catch (error) {
                    console.error('Handler error:', error);
                }
            });

        } catch (error) {
            console.error('Bitmap creation error:', error);
        }
    }

    private cleanupCameraResources(cameraId: string): void {
        // Clean up active bitmap for this camera
        const bitmap = this.activeBitmaps.get(cameraId);
        if (bitmap) {
            try {
                bitmap.close();
            } catch (e) {
                // Bitmap might already be closed
            }
            this.activeBitmaps.delete(cameraId);
        }
    }
}

// Export singleton instance
export const frameService = FrameService.getInstance();
