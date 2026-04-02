import React, { useEffect, useRef, useCallback } from 'react';

interface CameraTile {
    cameraId: string;
    element: HTMLElement;
}

interface TargetResolution {
    width: number;
    height: number;
}

interface PerCameraTarget {
    cameraId: string;
    width: number;
    height: number;
}

interface AdaptiveResolutionUpdate {
    uniform?: TargetResolution;
    perCamera?: PerCameraTarget[];
}

interface LiveCameraGridProps {
    cameraIds: string[];
    onResolutionUpdate?: (update: AdaptiveResolutionUpdate) => void;
    resizeThreshold?: number;
    debounceMs?: number;
    children?: (cameraId: string, ref: (el: HTMLElement | null) => void) => React.ReactNode;
}

const DEFAULT_RESIZE_THRESHOLD = 12;
const DEFAULT_DEBOUNCE_MS = 150;

export function LiveCameraGrid({
    cameraIds,
    onResolutionUpdate,
    resizeThreshold = DEFAULT_RESIZE_THRESHOLD,
    debounceMs = DEFAULT_DEBOUNCE_MS,
    children,
}: LiveCameraGridProps) {
    const tileRefs = useRef<Map<string, HTMLElement>>(new Map());
    const lastSentRef = useRef<Map<string, TargetResolution>>(new Map());
    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const observerRef = useRef<ResizeObserver | null>(null);

    const computePixelSize = useCallback((el: HTMLElement): TargetResolution => {
        const rect = el.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        return {
            width: Math.round(rect.width * dpr),
            height: Math.round(rect.height * dpr),
        };
    }, []);

    const hasChanged = useCallback(
        (cameraId: string, next: TargetResolution): boolean => {
            const prev = lastSentRef.current.get(cameraId);
            if (!prev) return true;
            return (
                Math.abs(next.width - prev.width) >= resizeThreshold ||
                Math.abs(next.height - prev.height) >= resizeThreshold
            );
        },
        [resizeThreshold]
    );

    const emitUpdate = useCallback(() => {
        if (!onResolutionUpdate) return;

        const updates: PerCameraTarget[] = [];

        tileRefs.current.forEach((el, cameraId) => {
            const size = computePixelSize(el);
            if (size.width > 0 && size.height > 0 && hasChanged(cameraId, size)) {
                updates.push({ cameraId, ...size });
                lastSentRef.current.set(cameraId, size);
            }
        });

        if (updates.length === 0) return;

        const allSameWidth = updates.every((u) => u.width === updates[0].width);
        const allSameHeight = updates.every((u) => u.height === updates[0].height);
        const allCamerasPresent = updates.length === tileRefs.current.size;

        if (allSameWidth && allSameHeight && allCamerasPresent) {
            onResolutionUpdate({
                uniform: { width: updates[0].width, height: updates[0].height },
            });
        } else {
            onResolutionUpdate({ perCamera: updates });
        }
    }, [onResolutionUpdate, computePixelSize, hasChanged]);

    const scheduleEmit = useCallback(() => {
        if (debounceTimerRef.current !== null) {
            clearTimeout(debounceTimerRef.current);
        }
        debounceTimerRef.current = setTimeout(() => {
            debounceTimerRef.current = null;
            emitUpdate();
        }, debounceMs);
    }, [emitUpdate, debounceMs]);

    useEffect(() => {
        observerRef.current = new ResizeObserver(() => {
            scheduleEmit();
        });

        tileRefs.current.forEach((el) => {
            observerRef.current!.observe(el);
        });

        return () => {
            observerRef.current?.disconnect();
            observerRef.current = null;
            if (debounceTimerRef.current !== null) {
                clearTimeout(debounceTimerRef.current);
                debounceTimerRef.current = null;
            }
        };
    }, [scheduleEmit]);

    const registerTile = useCallback(
        (cameraId: string) => (el: HTMLElement | null) => {
            const prev = tileRefs.current.get(cameraId);
            if (prev && observerRef.current) {
                observerRef.current.unobserve(prev);
            }
            if (el) {
                tileRefs.current.set(cameraId, el);
                if (observerRef.current) {
                    observerRef.current.observe(el);
                }
            } else {
                tileRefs.current.delete(cameraId);
                lastSentRef.current.delete(cameraId);
            }
        },
        []
    );

    return (
        <>
            {cameraIds.map((cameraId) =>
                children ? children(cameraId, registerTile(cameraId)) : null
            )}
        </>
    );
}

export type { LiveCameraGridProps, AdaptiveResolutionUpdate, PerCameraTarget, TargetResolution };
