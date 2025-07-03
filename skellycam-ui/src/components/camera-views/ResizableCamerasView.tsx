import React, {useEffect, useMemo, useRef, useState, useCallback} from 'react';
import {Box, CircularProgress, Paper, Typography, useTheme} from '@mui/material';
import {useAppSelector} from '@/store/AppStateStore';
import {CameraConfigsSchema} from "@/store/slices/cameras-slices/camera-types";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import { sortCamerasByIndex, useCameraGridLayout } from '@/hooks/useCameraGridLayout';

// Represents image data for a camera
interface ProcessedImageInfo {
    cameraId: string;
    aspectRatio: number; // width / height
    cameraIndex: number; // Added camera index for sorting
}

// Memoized camera panel component to reduce re-renders
const CameraPanel = React.memo(({
    image,
    cameraConfigs,
    canvasRef
}: {
    image: ProcessedImageInfo;
    cameraConfigs: Record<string, any>;
    canvasRef: (el: HTMLCanvasElement | null) => void;
}) => {
    const theme = useTheme();

    return (
        <Paper
            elevation={3}
            sx={{
                height: '100%',
                width: '100%',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
            }}
        >
            <Box
                sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    backgroundColor: 'rgba(0,0,0,0.5)',
                    color: 'white',
                    padding: '2px 8px',
                    borderBottomRightRadius: '4px',
                    fontSize: '0.8rem',
                    zIndex: 1,
                }}
            >
                Camera {cameraConfigs[image.cameraId]?.camera_index ?? '?'} ({image.cameraId})
            </Box>
            <Box
                sx={{
                    height: '100%',
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden',
                    padding: '4px',
                    boxSizing: 'border-box',
                }}
            >
                <canvas
                    ref={canvasRef}
                    style={{
                        maxWidth: '100%',
                        maxHeight: '100%',
                        objectFit: 'contain',
                    }}
                />
            </Box>
        </Paper>
    );
});

// Memoized resize handle to prevent unnecessary re-renders
const ResizeHandle = React.memo(({ direction, theme }: { direction: 'horizontal' | 'vertical', theme: any }) => (
    <PanelResizeHandle
        style={{
            [direction === 'horizontal' ? 'width' : 'height']: "2px",
            cursor: direction === 'horizontal' ? "col-resize" : "row-resize",
            backgroundColor: theme.palette.primary.dark,
        }}
    />
));

const ImageGrid: React.FC = () => {
    const theme = useTheme();
    const { latestImageBitmaps } = useWebSocketContext();
    const latestPayload = useAppSelector(state => state.latestPayload);
    const canvasContextRefs = useRef<Record<string, CanvasRenderingContext2D | null>>({});
    const dimensionsRef = useRef<Record<string, { width: number, height: number }>>({});

    // Safely parse camera configs with a fallback to empty object
    const cameraConfigs = useMemo(() => {
        if (!latestPayload.latestFrontendPayload?.camera_configs) return {};
        try {
            return CameraConfigsSchema.parse(latestPayload.latestFrontendPayload.camera_configs);
        } catch (e) {
            console.error('Failed to parse camera configs:', e);
            return {};
        }
    }, [latestPayload.latestFrontendPayload?.camera_configs]);

    // Refs for container and canvases
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRefs = useRef<Record<string, HTMLCanvasElement | null>>({});

    // Calculate image info and sort by camera index
    const sortedProcessedImages = useMemo(() => 
        sortCamerasByIndex(latestImageBitmaps, cameraConfigs),
    [latestImageBitmaps, cameraConfigs]);

    // Calculate optimal grid layout
    const initialLayout = useCameraGridLayout(sortedProcessedImages);

    // Optimize canvas drawing with requestAnimationFrame and offscreen canvas when available
    useEffect(() => {
        // Use requestAnimationFrame to batch canvas updates
        let animationFrameId: number;

        const updateCanvases = () => {
            Object.entries(latestImageBitmaps).forEach(([cameraId, bitmap]) => {
                const canvas = canvasRefs.current[cameraId];
                if (canvas) {
                    if (!canvasContextRefs.current[cameraId]) {
                        canvasContextRefs.current[cameraId] = canvas.getContext('2d', { alpha: false });
                    }
                    const ctx = canvasContextRefs.current[cameraId];
                    if (ctx) {
                        if (!dimensionsRef.current[cameraId] || 
                            dimensionsRef.current[cameraId].width !== bitmap.width || 
                            dimensionsRef.current[cameraId].height !== bitmap.height) {
                            
                            canvas.width = bitmap.width;
                            canvas.height = bitmap.height;
                            dimensionsRef.current[cameraId] = { width: bitmap.width, height: bitmap.height };
                        }

                        // Draw the bitmap
                        ctx.drawImage(bitmap, 0, 0);
                    }
                }
            });
        };

        animationFrameId = requestAnimationFrame(updateCanvases);

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [latestImageBitmaps]);

    // Memoized canvas ref callback
    const getCanvasRef = useCallback((cameraId: string) => {
        return (el: HTMLCanvasElement | null) => {
            canvasRefs.current[cameraId] = el;
        };
    }, []);

    // Create a nested panel structure - memoized to prevent unnecessary recalculations
    const panelStructure = useMemo(() => {
        if (sortedProcessedImages.length === 0) return null;

        // For a single camera, just render it directly
        if (sortedProcessedImages.length === 1) {
            const image = sortedProcessedImages[0];
            return (
                <CameraPanel
                    image={image}
                    cameraConfigs={cameraConfigs}
                    canvasRef={getCanvasRef(image.cameraId)}
                />
            );
        }

        // Create rows of panels
        const rows = [];
        const { rows: numRows, cols: numCols } = initialLayout;

        for (let r = 0; r < numRows; r++) {
            const rowCameras = sortedProcessedImages.slice(
                r * numCols,
                Math.min((r + 1) * numCols, sortedProcessedImages.length)
            );

            // Skip empty rows
            if (rowCameras.length === 0) continue;

            // For a single camera in a row, don't need inner PanelGroup
            if (rowCameras.length === 1) {
                rows.push(
                    <Panel key={`row-${r}`} defaultSize={100 / numRows}>
                        <CameraPanel
                            image={rowCameras[0]}
                            cameraConfigs={cameraConfigs}
                            canvasRef={getCanvasRef(rowCameras[0].cameraId)}
                        />
                    </Panel>
                );

                // Add resize handle if not the last row
                if (r < numRows - 1) {
                    rows.push(
                        <ResizeHandle key={`row-handle-${r}`} direction="vertical" theme={theme} />
                    );
                }
                continue;
            }

            // Create a row with multiple cameras
            const rowContent = (
                <PanelGroup direction="horizontal">
                    {rowCameras.map((image, colIndex) => (
                        <React.Fragment key={image.cameraId}>
                            {colIndex > 0 && (
                                <ResizeHandle direction="horizontal" theme={theme} />
                            )}
                            <Panel defaultSize={100 / rowCameras.length}>
                                <CameraPanel
                                    image={image}
                                    cameraConfigs={cameraConfigs}
                                    canvasRef={getCanvasRef(image.cameraId)}
                                />
                            </Panel>
                        </React.Fragment>
                    ))}
                </PanelGroup>
            );

            rows.push(
                <Panel key={`row-${r}`} defaultSize={100 / numRows}>
                    {rowContent}
                </Panel>
            );

            // Add resize handle if not the last row
            if (r < numRows - 1) {
                rows.push(
                    <ResizeHandle key={`row-handle-${r}`} direction="vertical" theme={theme} />
                );
            }
        }

        return rows;
    }, [sortedProcessedImages, initialLayout, cameraConfigs, theme, getCanvasRef]);

    return (
        <Box
            ref={containerRef}
            sx={{
                width: '100%',
                height: '100%',
                backgroundColor: theme.palette.background.default,
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
            }}
        >
            {sortedProcessedImages.length === 0 ? (
                <Box
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                    }}
                >
                    <Typography variant="h6" color="text.secondary">
                        Waiting for camera feeds...
                    </Typography>
                </Box>
            ) : (
                <PanelGroup direction="vertical" style={{ height: '100%' }}>
                    {panelStructure}
                </PanelGroup>
            )}
        </Box>
    );
};

// Memoize the entire CameraGridDisplay component to prevent unnecessary re-renders
const ResizableCameraGridDisplay: React.FC = React.memo(() => {
    const {latestImageBitmaps, isConnected} = useWebSocketContext();
    const [isLoading, setIsLoading] = useState(true);
    const hasImages = Object.keys(latestImageBitmaps).length > 0;

    // Set loading state based on connection and images
    useEffect(() => {
        if (isConnected) {
            // If connected, wait a short time for images
            const timeout = setTimeout(() => {
                setIsLoading(false);
            }, 3000);

            return () => clearTimeout(timeout);
        } else {
            // If not connected, keep loading state
            setIsLoading(true);
        }
    }, [isConnected]);

    return (
        <Box
            sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                position: 'relative',
            }}
        >
            {isLoading ? (
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                        gap: 2,
                    }}
                >
                    <CircularProgress/>
                    <Typography variant="h6" color="text.secondary">
                        Connecting to camera feed...
                    </Typography>
                </Box>
            ) : !hasImages ? (
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                    }}
                >
                    <Typography variant="h6" color="text.secondary">
                        No camera feeds available
                    </Typography>
                </Box>
            ) : (
                <Box
                    sx={{
                        flexGrow: 1,
                        width: '100%',
                        overflow: 'hidden',
                    }}
                >
                    <ImageGrid/>
                </Box>
            )}
        </Box>
    );
});

export default ResizableCameraGridDisplay;
