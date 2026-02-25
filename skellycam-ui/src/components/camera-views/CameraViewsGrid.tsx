import React, { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Box, IconButton, Tooltip } from "@mui/material";
import GridViewIcon from '@mui/icons-material/GridView';
import { ResizableCameraView } from "./ResizableCameraView";
import { useServer } from "@/services/server/ServerContextProvider";
import { useTranslation } from 'react-i18next';

const GAP = 4;

interface CameraLayout {
    x: number;
    y: number;
    w: number;
    h: number;
}

/**
 * Compute an auto-layout that tiles cameras to aggressively fill
 * the available container width × height.
 * Tries column counts from 1..N and picks the arrangement that
 * maximizes total pixel area used by cameras.
 */
function computeAutoLayout(
    cameraIds: string[],
    containerWidth: number,
    containerHeight: number,
): Record<string, CameraLayout> {
    const n = cameraIds.length;
    if (n === 0 || containerWidth <= 0 || containerHeight <= 0) return {};

    let bestLayouts: Record<string, CameraLayout> = {};
    let bestArea = 0;

    // Try every possible column count and pick the one that fills the most area
    for (let cols = 1; cols <= n; cols++) {
        const rows = Math.ceil(n / cols);
        const cellW = (containerWidth - GAP * (cols - 1)) / cols;
        const cellH = (containerHeight - GAP * (rows - 1)) / rows;

        if (cellW < 80 || cellH < 60) continue;

        let totalArea = 0;
        const layouts: Record<string, CameraLayout> = {};

        for (let i = 0; i < n; i++) {
            const col = i % cols;
            const row = Math.floor(i / cols);
            const w = cellW;
            const h = cellH;
            const x = col * (cellW + GAP);
            const y = row * (cellH + GAP);
            layouts[cameraIds[i]] = { x, y, w, h };
            totalArea += w * h;
        }

        if (totalArea > bestArea) {
            bestArea = totalArea;
            bestLayouts = layouts;
        }
    }

    return bestLayouts;
}

interface CameraViewsGridProps {
    settings?: { columns: number | null };
}

export const CameraViewsGrid: React.FC<CameraViewsGridProps> = ({ settings }) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const containerRef = useRef<HTMLDivElement>(null);

    const [containerSize, setContainerSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
    const [layouts, setLayouts] = useState<Record<string, CameraLayout>>({});
    const [zIndices, setZIndices] = useState<Record<string, number>>({});
    const [zCounter, setZCounter] = useState<number>(1);
    // Incremented to force a re-layout from auto-layout computation
    const [layoutVersion, setLayoutVersion] = useState<number>(0);

    // Observe container size
    useEffect(() => {
        const el = containerRef.current;
        if (!el) return;

        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                const { width, height } = entry.contentRect;
                setContainerSize({ w: width, h: height });
            }
        });
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    // Compute auto layout when cameras or container size change
    const autoLayout = useMemo(() => {
        return computeAutoLayout(connectedCameraIds, containerSize.w, containerSize.h);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [connectedCameraIds, containerSize.w, containerSize.h, layoutVersion]);

    // Apply auto layout on mount, when cameras change, or on reset
    useEffect(() => {
        setLayouts(autoLayout);
        // Reset z-indices
        const zMap: Record<string, number> = {};
        connectedCameraIds.forEach((id, i) => { zMap[id] = i + 1; });
        setZIndices(zMap);
        setZCounter(connectedCameraIds.length + 1);
    }, [autoLayout, connectedCameraIds]);

    const handleLayoutChange = useCallback(
        (cameraId: string, x: number, y: number, w: number, h: number) => {
            setLayouts(prev => ({ ...prev, [cameraId]: { x, y, w, h } }));
        },
        [],
    );

    const handleFocus = useCallback((cameraId: string) => {
        setZCounter(prev => {
            const next = prev + 1;
            setZIndices(prevZ => ({ ...prevZ, [cameraId]: next }));
            return next;
        });
    }, []);

    const handleResetLayout = useCallback(() => {
        setLayoutVersion(v => v + 1);
    }, []);

    if (connectedCameraIds.length === 0) {
        return (
            <Box sx={{
                height: '100%',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'text.secondary',
                fontSize: '1.2rem',
                padding: 4,
                textAlign: 'center',
            }}>
                <div>
                    <div>{t('noCamerasConnected')}</div>
                    <div style={{ fontSize: '0.9rem', marginTop: '0.5rem' }}>
                        {t('waitingForCameraStreams')}
                    </div>
                </div>
            </Box>
        );
    }

    return (
        <Box
            ref={containerRef}
            sx={{
                position: 'relative',
                width: '100%',
                height: '100%',
                minHeight: 300,
                overflow: 'hidden',
            }}
        >
            {/* Reset layout button */}
            <Tooltip title="Reset camera layout">
                <IconButton
                    onClick={handleResetLayout}
                    size="small"
                    sx={{
                        position: 'absolute',
                        top: 8,
                        left: 8,
                        zIndex: 9999,
                        backgroundColor: 'rgba(0,0,0,0.6)',
                        color: '#fff',
                        '&:hover': { backgroundColor: 'rgba(0,0,0,0.8)' },
                    }}
                >
                    <GridViewIcon fontSize="small" />
                </IconButton>
            </Tooltip>

            {connectedCameraIds.map(cameraId => {
                const layout = layouts[cameraId];
                if (!layout) return null;

                return (
                    <ResizableCameraView
                        key={cameraId}
                        cameraId={cameraId}
                        initialX={layout.x}
                        initialY={layout.y}
                        initialWidth={layout.w}
                        initialHeight={layout.h}
                        onLayoutChange={handleLayoutChange}
                        onFocus={handleFocus}
                        zIndex={zIndices[cameraId] ?? 1}
                    />
                );
            })}
        </Box>
    );
};
