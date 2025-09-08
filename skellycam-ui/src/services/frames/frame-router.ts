// ============================================
// FRAME ROUTER (frame-router.ts)
// ============================================
// High-performance frame routing and metadata management for multicamera streaming


// Type definitions
import {BinaryFrameParser, ParsedFrame, ParsedPayload} from "@/services/frames/binary-frame-processor";
import {websocketManager} from "@/services";

export interface FrameMetadata {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    timestamp: number;
    width: number;
    height: number;
    fps?: number;
}

export interface FrameAcknowledgment {
    frameNumber: number;
    displaySizes: Record<string, { width: number; height: number }>;
}

export type FrameHandler = (
    bitmap: ImageBitmap,
    metadata: FrameMetadata
) => void;

export type MetadataChangeHandler = (metadata: Map<string, FrameMetadata>) => void;

interface FrameCounter {
    count: number;
    startTime: number;
    fps: number;
}

interface FrameRouterOptions {
    enablePerformanceWarnings?: boolean;
    maxProcessingTimeMs?: number;
    staleTimeoutMs?: number;
    fpsUpdateIntervalMs?: number;
}

/**
 * Frame Router - manages frame distribution and metadata for multicamera streaming
 */
class FrameRouter {
    private static instance: FrameRouter;

    // Core components
    private parser: BinaryFrameParser;
    private handlers = new Map<string, Set<FrameHandler>>();

    // Metadata management
    private frameMetadata = new Map<string, FrameMetadata>();
    private metadataChangeHandlers = new Set<MetadataChangeHandler>();

    // Performance tracking
    private frameCounters = new Map<string, FrameCounter>();
    private fpsUpdateInterval: number | null = null;

    // Configuration
    private options: Required<FrameRouterOptions> = {
        enablePerformanceWarnings: true,
        maxProcessingTimeMs: 16.67, // 60fps frame time
        staleTimeoutMs: 5000,
        fpsUpdateIntervalMs: 1000,
    };

    // Statistics
    private stats = {
        totalFramesProcessed: 0,
        totalFramesDropped: 0,
        lastProcessingTime: 0,
    };

    private constructor(options?: FrameRouterOptions) {
        if (options) {
            this.options = { ...this.options, ...options };
        }

        this.parser = new BinaryFrameParser({
            parseWarningsEnabled: this.options.enablePerformanceWarnings,
            maxParseTimeMs: 5,
        });
    }

    static getInstance(options?: FrameRouterOptions): FrameRouter {
        if (!FrameRouter.instance) {
            FrameRouter.instance = new FrameRouter(options);
        }
        return FrameRouter.instance;
    }

    // ============================================
    // LIFECYCLE METHODS
    // ============================================

    initialize(): void {
        // Register binary handler with WebSocket manager
        websocketManager.addBinaryHandler((data: ArrayBuffer) => {
            this.processBinaryFrame(data);
        });

        // Start FPS update timer
        this.startFPSUpdates();

        console.log('FrameRouter initialized with options:', this.options);
    }

    destroy(): void {
        this.stopFPSUpdates();
        this.handlers.clear();
        this.frameMetadata.clear();
        this.metadataChangeHandlers.clear();
        this.frameCounters.clear();

        console.log('FrameRouter destroyed. Stats:', this.getStats());
    }

    // ============================================
    // PUBLIC API - SUBSCRIPTIONS
    // ============================================

    /**
     * Subscribe to frame updates for a specific camera
     */
    subscribe(cameraId: string, handler: FrameHandler): () => void {
        if (!this.handlers.has(cameraId)) {
            this.handlers.set(cameraId, new Set());
        }
        this.handlers.get(cameraId)!.add(handler);

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

    /**
     * Subscribe to metadata changes for all cameras
     */
    subscribeToMetadataChanges(handler: MetadataChangeHandler): () => void {
        this.metadataChangeHandlers.add(handler);

        // Immediately call with current metadata
        handler(new Map(this.frameMetadata));

        return () => {
            this.metadataChangeHandlers.delete(handler);
        };
    }

    // ============================================
    // PUBLIC API - METADATA ACCESS
    // ============================================

    /**
     * Get current metadata for a specific camera
     */
    getCameraMetadata(cameraId: string): FrameMetadata | undefined {
        return this.frameMetadata.get(cameraId);
    }

    /**
     * Get all camera metadata
     */
    getAllCameraMetadata(): Map<string, FrameMetadata> {
        return new Map(this.frameMetadata);
    }

    /**
     * Get list of active camera IDs
     */
    getActiveCameraIds(): string[] {
        return Array.from(this.frameMetadata.keys());
    }

    /**
     * Get current FPS for a camera
     */
    getCameraFPS(cameraId: string): number | null {
        const counter = this.frameCounters.get(cameraId);
        return counter?.fps ?? null;
    }

    /**
     * Get performance statistics
     */
    getStats() {
        return {
            ...this.stats,
            activeCameras: this.frameMetadata.size,
            subscribedCameras: this.handlers.size,
        };
    }

    // ============================================
    // PUBLIC API - MANAGEMENT
    // ============================================

    /**
     * Remove a camera and its metadata
     */
    removeCamera(cameraId: string): void {
        this.frameMetadata.delete(cameraId);
        this.frameCounters.delete(cameraId);
        this.handlers.delete(cameraId);
        this.notifyMetadataChange();
    }

    /**
     * Remove stale cameras that haven't received frames recently
     */
    removeStaleCamera(cameraId: string): void {
        this.frameMetadata.delete(cameraId);
        this.frameCounters.delete(cameraId);
        this.notifyMetadataChange();
    }

    /**
     * Check for and remove stale cameras
     */
    checkForStaleCameras(): string[] {
        const now = Date.now();
        const staleCameras: string[] = [];

        for (const [cameraId, metadata] of this.frameMetadata.entries()) {
            if (now - metadata.timestamp > this.options.staleTimeoutMs) {
                staleCameras.push(cameraId);
                this.removeStaleCamera(cameraId);
            }
        }

        if (staleCameras.length > 0) {
            console.warn(`Removed ${staleCameras.length} stale cameras:`, staleCameras);
        }

        return staleCameras;
    }

    /**
     * Update configuration options
     */
    updateOptions(options: Partial<FrameRouterOptions>): void {
        this.options = { ...this.options, ...options };

        // Update parser if performance warnings changed
        if (options.enablePerformanceWarnings !== undefined) {
            this.parser = new BinaryFrameParser({
                parseWarningsEnabled: options.enablePerformanceWarnings,
            });
        }

        // Restart FPS updates if interval changed
        if (options.fpsUpdateIntervalMs !== undefined) {
            this.stopFPSUpdates();
            this.startFPSUpdates();
        }
    }

    // ============================================
    // PRIVATE METHODS - FRAME PROCESSING
    // ============================================

    private async processBinaryFrame(data: ArrayBuffer): Promise<void> {
        const processingStart = performance.now();

        try {
            // Parse the binary data
            const payload = this.parser.parseFrameData(data);
            if (!payload) {
                this.stats.totalFramesDropped++;
                return;
            }

            // Process the parsed payload
            await this.processPayload(payload);

            // Send acknowledgment
            this.sendFrameAcknowledgment(payload);

        } catch (error) {
            console.error('Frame processing error:', error);
            this.stats.totalFramesDropped++;
        } finally {
            // Track processing time
            const processingTime = performance.now() - processingStart;
            this.stats.lastProcessingTime = processingTime;

            if (this.options.enablePerformanceWarnings &&
                processingTime > this.options.maxProcessingTimeMs) {
                console.warn(
                    `Frame processing took ${processingTime.toFixed(2)}ms ` +
                    `(threshold: ${this.options.maxProcessingTimeMs}ms)`
                );
            }
        }
    }

    private async processPayload(payload: ParsedPayload): Promise<void> {
        let metadataChanged = false;
        const bitmapPromises: Promise<void>[] = [];

        for (const frame of payload.frames) {
            // Update metadata
            if (this.updateFrameMetadata(frame)) {
                metadataChanged = true;
            }

            // Update frame counter
            this.incrementFrameCounter(frame.cameraId);
            this.stats.totalFramesProcessed++;

            // Skip if no subscribers
            const handlers = this.handlers.get(frame.cameraId);
            if (!handlers || handlers.size === 0) {
                continue;
            }

            // Create bitmap and notify handlers
            const promise = this.processFrame(frame, handlers);
            bitmapPromises.push(promise);
        }

        // Notify metadata changes if needed
        if (metadataChanged) {
            this.notifyMetadataChange();
        }

        // Wait for all bitmaps to be processed
        await Promise.all(bitmapPromises);
    }

    private async processFrame(
        frame: ParsedFrame,
        handlers: Set<FrameHandler>
    ): Promise<void> {
        try {
            // Create blob and bitmap
            const blob = new Blob([frame.jpegData], { type: 'image/jpeg' });
            const bitmap = await createImageBitmap(blob, {
                premultiplyAlpha: 'none',
                colorSpaceConversion: 'none',
            });

            // Get current metadata with latest FPS
            const metadata = this.frameMetadata.get(frame.cameraId);
            if (!metadata) {
                bitmap.close();
                return;
            }

            // Notify all handlers
            handlers.forEach(handler => {
                try {
                    handler(bitmap, { ...metadata });
                } catch (error) {
                    console.error(`Frame handler error for camera ${frame.cameraId}:`, error);
                }
            });

            // Schedule bitmap cleanup
            requestAnimationFrame(() => {
                bitmap.close();
            });

        } catch (error) {
            console.error(`Failed to create bitmap for camera ${frame.cameraId}:`, error);
            this.stats.totalFramesDropped++;
        }
    }

    // ============================================
    // PRIVATE METHODS - METADATA MANAGEMENT
    // ============================================

    private updateFrameMetadata(frame: ParsedFrame): boolean {
        const existing = this.frameMetadata.get(frame.cameraId);

        if (!existing ||
            existing.width !== frame.width ||
            existing.height !== frame.height ||
            existing.cameraIndex !== frame.cameraIndex) {

            this.frameMetadata.set(frame.cameraId, {
                cameraId: frame.cameraId,
                cameraIndex: frame.cameraIndex,
                frameNumber: frame.frameNumber,
                timestamp: Date.now(),
                width: frame.width,
                height: frame.height,
                fps: 0,
            });
            return true;
        }

        // Update existing metadata
        existing.frameNumber = frame.frameNumber;
        existing.timestamp = Date.now();
        return false;
    }

    private notifyMetadataChange(): void {
        const metadataCopy = new Map(this.frameMetadata);
        this.metadataChangeHandlers.forEach(handler => {
            try {
                handler(metadataCopy);
            } catch (error) {
                console.error('Metadata change handler error:', error);
            }
        });
    }

    // ============================================
    // PRIVATE METHODS - PERFORMANCE TRACKING
    // ============================================

    private startFPSUpdates(): void {
        this.stopFPSUpdates();

        this.fpsUpdateInterval = window.setInterval(() => {
            this.updateAllFPS();
        }, this.options.fpsUpdateIntervalMs);
    }

    private stopFPSUpdates(): void {
        if (this.fpsUpdateInterval !== null) {
            clearInterval(this.fpsUpdateInterval);
            this.fpsUpdateInterval = null;
        }
    }

    private updateAllFPS(): void {
        const now = Date.now();
        let hasChanges = false;

        for (const [cameraId, counter] of this.frameCounters.entries()) {
            const elapsed = now - counter.startTime;
            if (elapsed >= this.options.fpsUpdateIntervalMs) {
                const newFPS = Math.round((counter.count / elapsed) * 1000);

                counter.fps = newFPS;
                counter.count = 0;
                counter.startTime = now;

                const metadata = this.frameMetadata.get(cameraId);
                if (metadata && metadata.fps !== newFPS) {
                    metadata.fps = newFPS;
                    hasChanges = true;
                }
            }
        }

        if (hasChanges) {
            this.notifyMetadataChange();
        }
    }

    private incrementFrameCounter(cameraId: string): void {
        const now = Date.now();
        let counter = this.frameCounters.get(cameraId);

        if (!counter) {
            counter = { count: 1, startTime: now, fps: 0 };
            this.frameCounters.set(cameraId, counter);
        } else {
            counter.count++;
        }
    }

    // ============================================
    // PRIVATE METHODS - NETWORK
    // ============================================

    private sendFrameAcknowledgment(payload: ParsedPayload): void {
        const ack: FrameAcknowledgment = {
            frameNumber: payload.frameNumber,
            displaySizes: payload.frames.reduce((acc: { [x: string]: { width: any; height: any; }; }, frame: { cameraId: string | number; width: any; height: any; }) => {
                acc[frame.cameraId] = {
                    width: frame.width,
                    height: frame.height
                };
                return acc;
            }, {} as Record<string, { width: number; height: number }>)
        };

        websocketManager.send(JSON.stringify({
            type: 'frame_ack',
            frame_number: ack.frameNumber,
            display_sizes: ack.displaySizes,
        }));
    }
}

export const frameRouter = FrameRouter.getInstance();
