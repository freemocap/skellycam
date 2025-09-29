import {workerCode} from "@/services/server/server-helpers/offscreen-renderer.worker";


export interface FrameData {
    cameraId: string;
    frameNumber: number;
    bitmap: ImageBitmap;
}


export interface CanvasWorker {
    worker: Worker;
    canvas: HTMLCanvasElement;
    initialized: boolean;
}

export class CanvasManager {
    private workers: Map<string, CanvasWorker> = new Map();
    private workerErrors: Map<string, number> = new Map();
    private maxWorkerErrors: number = 3;

    public setCanvasForCamera(cameraId: string, canvas: HTMLCanvasElement): boolean {
        // Check if this exact canvas is already set
        const existing = this.workers.get(cameraId);
        if (existing?.canvas === canvas && existing.initialized) {
            return true;
        }

        // Clean up existing worker
        this.terminateWorker(cameraId);

        try {
            const worker = this.createWorker(cameraId);
            const offscreen = canvas.transferControlToOffscreen();

            worker.postMessage(
                { type: 'init', canvas: offscreen },
                [offscreen]
            );

            this.workers.set(cameraId, {
                worker,
                canvas,
                initialized: true
            });

            // Reset error count on successful creation
            this.workerErrors.delete(cameraId);
            return true;

        } catch (error) {
            console.error(`Failed to create worker for camera ${cameraId}:`, error);
            this.recordWorkerError(cameraId);
            return false;
        }
    }

    public sendFrameToWorker(cameraId: string, bitmap: ImageBitmap): boolean {
        const workerInfo = this.workers.get(cameraId);

        if (!workerInfo?.initialized) {
            bitmap.close(); // Clean up bitmap
            return false;
        }

        try {
            workerInfo.worker.postMessage(
                { type: 'frame', bitmap },
                [bitmap]
            );
            return true;
        } catch (error) {
            console.error(`Failed to send frame to worker ${cameraId}:`, error);
            bitmap.close();
            this.recordWorkerError(cameraId);
            return false;
        }
    }

    public terminateWorker(cameraId: string): void {
        const workerInfo = this.workers.get(cameraId);
        if (workerInfo) {
            try {
                workerInfo.worker.terminate();
            } catch (error) {
                console.error(`Error terminating worker for ${cameraId}:`, error);
            }
            this.workers.delete(cameraId);
        }
    }

    public terminateAllWorkers(): void {
        for (const [cameraId] of this.workers) {
            this.terminateWorker(cameraId);
        }
        this.workerErrors.clear();
    }

    private createWorker(cameraId: string): Worker {
        const blob = new Blob([workerCode], { type: 'application/javascript' });
        const workerUrl = URL.createObjectURL(blob);

        try {
            const worker = new Worker(workerUrl);

            // Set up error handling
            worker.onerror = (error) => {
                console.error(`Worker error for camera ${cameraId}:`, error);
                this.recordWorkerError(cameraId);
            };

            worker.onmessageerror = (error) => {
                console.error(`Worker message error for camera ${cameraId}:`, error);
            };

            return worker;
        } finally {
            URL.revokeObjectURL(workerUrl);
        }
    }

    private recordWorkerError(cameraId: string): void {
        const errorCount = (this.workerErrors.get(cameraId) ?? 0) + 1;
        this.workerErrors.set(cameraId, errorCount);

        if (errorCount >= this.maxWorkerErrors) {
            console.error(`Worker for camera ${cameraId} has failed ${errorCount} times, disabling`);
            this.terminateWorker(cameraId);
        }
    }

    public getWorkerStatus(cameraId: string): { hasWorker: boolean; errorCount: number } {
        return {
            hasWorker: this.workers.has(cameraId),
            errorCount: this.workerErrors.get(cameraId) ?? 0
        };
    }
}
