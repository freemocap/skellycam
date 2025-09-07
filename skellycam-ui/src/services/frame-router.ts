import {websocketManager} from "@/services/api";

//  FRAME ROUTER (Binary Data Handler)

import { store } from '../store/store';
import { frameMetadataUpdated } from '../store/slices/websocket/websocket-slice';

export type FrameHandler = (
    bitmap: ImageBitmap,
    metadata: {
        frameNumber: number;
        timestamp: number;
        width: number;
        height: number;
    }
) => void;

class FrameRouter {
    private static instance: FrameRouter;
    private handlers = new Map<string, Set<FrameHandler>>();
    private frameStats = new Map<string, { count: number; lastTime: number }>();

    private constructor() {}

    static getInstance(): FrameRouter {
        if (!FrameRouter.instance) {
            FrameRouter.instance = new FrameRouter();
        }
        return FrameRouter.instance;
    }

    initialize(): void {
        // Register binary handler with WebSocket manager
        websocketManager.addBinaryHandler((data: ArrayBuffer) => {
            this.processBinaryMessage(data).then(r => {}).catch(
                error => console.error('Error in processBinaryMessage:', error)
            )

        });
    }

    subscribe(cameraId: string, handler: FrameHandler): () => void {
        if (!this.handlers.has(cameraId)) {
            this.handlers.set(cameraId, new Set());
        }
        this.handlers.get(cameraId)!.add(handler);

        // Return unsubscribe function
        return () => {
            this.handlers.get(cameraId)?.delete(handler);
            if (this.handlers.get(cameraId)?.size === 0) {
                this.handlers.delete(cameraId);
            }
        };
    }

    private async processBinaryMessage(data: ArrayBuffer): Promise<void> {
        try {
            const frames = await this.parseFrameData(data);

            for (const frame of frames) {
                const handlers = this.handlers.get(frame.cameraId);

                // Skip processing if no one is watching
                if (!handlers || handlers.size === 0) {
                    continue;
                }

                // Create ImageBitmap
                const blob = new Blob([frame.jpegData], { type: 'image/jpeg' });
                const bitmap = await createImageBitmap(blob, {
                    premultiplyAlpha: 'none',
                    colorSpaceConversion: 'none',
                    resizeQuality: 'pixelated',
                });

                const metadata = {
                    frameNumber: frame.frameNumber,
                    timestamp: Date.now(),
                    width: frame.width,
                    height: frame.height,
                };

                // Update Redux metadata
                store.dispatch(frameMetadataUpdated({
                    cameraId: frame.cameraId,
                    ...metadata,
                }));

                // Send to all handlers
                handlers.forEach(handler => handler(bitmap, metadata));

                // Clean up bitmap after frame
                requestAnimationFrame(() => bitmap.close());
            }
        } catch (error) {
            console.error('Error processing binary frame:', error);
        }
    }

    private async parseFrameData(data: ArrayBuffer): Promise<any[]> {
        const frames = [];
        const dataView = new DataView(data);
        const textDecoder = new TextDecoder();
        let offset = 0;

        // Parse payload header
        const frameNumber = Number(dataView.getBigInt64(8, true));
        const numCameras = dataView.getInt32(16, true);
        offset += 24; // Header size

        for (let i = 0; i < numCameras; i++) {
            // Parse frame header
            offset += 8; // Skip message type and padding

            // Extract camera ID
            const cameraIdBytes = new Uint8Array(data, offset + 8, 16);
            const cameraId = textDecoder.decode(cameraIdBytes).replace(/\0/g, '');

            const width = dataView.getInt32(offset + 32, true);
            const height = dataView.getInt32(offset + 36, true);
            const jpegLength = dataView.getInt32(offset + 44, true);
            offset += 56; // Frame header size

            // Extract JPEG data
            const jpegData = new Uint8Array(data, offset, jpegLength);
            offset += jpegLength;

            frames.push({
                cameraId,
                frameNumber,
                width,
                height,
                jpegData,
            });
        }

        return frames;
    }

    getFrameRate(cameraId: string): number {
        const stats = this.frameStats.get(cameraId);
        if (!stats) return 0;

        const now = Date.now();
        const elapsed = now - stats.lastTime;
        const fps = (stats.count / elapsed) * 1000;

        return Math.round(fps);
    }
}

export const frameRouter = FrameRouter.getInstance();
