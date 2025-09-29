import {parseMultiFramePayload} from "@/services/server/server-helpers/frame-processor/binary-frame-parser";
import {FrameData} from "@/services/server/server-helpers/canvas-manager";
export interface ProcessedFrameResult {
    frames: FrameData[];
    cameraIds: Set<string>;
    frameNumbers: Set<number>;
}

export class FrameProcessor {
    private frameDropCount: Map<string, number> = new Map();
    private lastFrameTime: Map<string, number> = new Map();

    public async processFramePayload(data: ArrayBuffer): Promise<ProcessedFrameResult | null> {
        try {
            const frames = await parseMultiFramePayload(data);
            if (!frames) {
                console.warn('Failed to parse frame payload');
                return null;
            }

            const cameraIds = new Set<string>();
            const frameNumbers = new Set<number>();

            for (const frame of frames) {
                cameraIds.add(frame.cameraId);
                frameNumbers.add(frame.frameNumber);

                // Track frame timing for performance monitoring
                const now = performance.now();
                const lastTime = this.lastFrameTime.get(frame.cameraId);
                if (lastTime) {
                    const fps = 1000 / (now - lastTime);
                    if (fps < 20) { // Below 20 FPS warning
                        console.warn(`Low FPS for camera ${frame.cameraId}: ${fps.toFixed(1)}`);
                    }
                }
                this.lastFrameTime.set(frame.cameraId, now);
            }

            return {frames, cameraIds, frameNumbers};
        } catch (error) {
            console.error('Error processing frame payload:', error);
            throw new Error(`Frame processing failed: ${error}`);
        }
    }

    public recordDroppedFrame(cameraId: string): void {
        const current = this.frameDropCount.get(cameraId) ?? 0;
        this.frameDropCount.set(cameraId, current + 1);

        if ((current + 1) % 100 === 0) {
            console.warn(`Camera ${cameraId} has dropped ${current + 1} frames`);
        }
    }

    public getStats(cameraId: string): { droppedFrames: number; lastFrameTime: number | undefined } {
        return {
            droppedFrames: this.frameDropCount.get(cameraId) ?? 0,
            lastFrameTime: this.lastFrameTime.get(cameraId)
        };
    }

    public reset(): void {
        this.frameDropCount.clear();
        this.lastFrameTime.clear();
    }
}
