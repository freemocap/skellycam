import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Box, CircularProgress, Paper, Typography, useTheme} from '@mui/material';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {useCameraGridLayout} from '@/hooks/useCameraGridLayout';
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {FrameRenderAcknowledgment} from "@/context/websocket-context/useWebSocket";
import {PlaceholderImage} from "@/components/camera-views/threejs-strategy/threejs-helper-components/PlaceholderImage";


const CameraCanvasPanel = React.memo(({
                                          cameraImageData,
                                          canvasRef
                                      }: {
    cameraImageData: CameraImageData;
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
                Camera {cameraImageData.cameraIndex ?? '?'} ({cameraImageData.cameraId})
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

const ResizeHandle = React.memo(({direction, theme}: { direction: 'horizontal' | 'vertical', theme: any }) => (
    <PanelResizeHandle
        style={{
            [direction === 'horizontal' ? 'width' : 'height']: "2px",
            cursor: direction === 'horizontal' ? "col-resize" : "row-resize",
            backgroundColor: theme.palette.primary.dark,
        }}
    />
));

const CameraCanvasGridPanel: React.FC = () => {
    const theme = useTheme();
    const {latestImageData, sendFrameAcknowledgment} = useWebSocketContext();
    const canvasContextRefs = useRef<Record<string, CanvasRenderingContext2D | null>>({});
    const dimensionsRef = useRef<Record<string, { width: number, height: number }>>({});


    // Refs for container and canvases
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRefs = useRef<Record<string, HTMLCanvasElement | null>>({});


    // Calculate optimal grid layout

    const initialLayout = useCameraGridLayout(latestImageData, containerRef.current?.clientWidth, containerRef.current?.clientHeight);

    // Optimize canvas drawing with requestAnimationFrame and offscreen canvas when available
    useEffect(() => {
        // Use requestAnimationFrame to batch canvas updates
        let animationFrameId: number;

        const updateCanvases = () => {
            const frameRenderAcknowledgment: FrameRenderAcknowledgment = {
                frameNumber: -1,
                cameraDisplaySizes: {}
            }
            Object.entries(latestImageData).forEach(([cameraId, cameraImageData]) => {
                const canvas = canvasRefs.current[cameraId];
                if (canvas) {
                    if (!canvasContextRefs.current[cameraId]) {
                        canvasContextRefs.current[cameraId] = canvas.getContext('2d', {alpha: false});
                    }
                    const ctx = canvasContextRefs.current[cameraId];
                    if (ctx) {
                        if (!dimensionsRef.current[cameraId] ||
                            dimensionsRef.current[cameraId].width !== cameraImageData.imageBitmap.width ||
                            dimensionsRef.current[cameraId].height !== cameraImageData.imageBitmap.height) {

                            canvas.width = cameraImageData.imageBitmap.width;
                            canvas.height = cameraImageData.imageBitmap.height;
                            dimensionsRef.current[cameraId] = {
                                width: cameraImageData.imageBitmap.width,
                                height: cameraImageData.imageBitmap.height
                            };
                        }

                        // Draw the bitmap
                        ctx.drawImage(cameraImageData.imageBitmap, 0, 0);
                    }
                }
                if (!(frameRenderAcknowledgment.frameNumber === -1) &&
                    !(cameraImageData.frameNumber === frameRenderAcknowledgment.frameNumber)) {
                    throw new Error(`Frame number mismatch for camera ${cameraId}: expected ${frameRenderAcknowledgment.frameNumber}, got ${cameraImageData.frameNumber}`);
                }
                frameRenderAcknowledgment.frameNumber = cameraImageData.frameNumber;
                frameRenderAcknowledgment.cameraDisplaySizes[cameraId] = {
                    cameraId: cameraImageData.cameraId,
                    imageDisplayWidth: cameraImageData.imageBitmap.width, // TODO - send actual display size
                    imageDisplayHeight: cameraImageData.imageBitmap.height // TODO - send actual display size
                };
            });
            // Send acknowledgment after all canvases are updated
            console.log("Sending frame acknowledgment:", frameRenderAcknowledgment);
            sendFrameAcknowledgment(frameRenderAcknowledgment);
        };

        animationFrameId = requestAnimationFrame(updateCanvases);

        return () => {
            cancelAnimationFrame(animationFrameId);
        };
    }, [latestImageData]);

    // Memoized canvas ref callback
    const getCanvasRef = useCallback((cameraId: string) => {
        return (el: HTMLCanvasElement | null) => {
            canvasRefs.current[cameraId] = el;
        };
    }, []);

    // Create a nested panel structure - memoized to prevent unnecessary recalculations
    const panelStructure = useMemo(() => {
        if (sortedCameraImageDataArray.length === 0) return null;

        // Create rows of panels
        const rows = [];
        const {rows: numRows, columns: numCols} = initialLayout;

        for (let r = 0; r < numRows; r++) {
            const rowCameras = sortedCameraImageDataArray.slice(
                r * numCols,
                Math.min((r + 1) * numCols, sortedCameraImageDataArray.length)
            );

            // Skip empty rows
            if (rowCameras.length === 0) continue;

            // Create a row with multiple cameras
            const rowContent = (
                <PanelGroup direction="horizontal">
                    {rowCameras.map((image, colIndex) => (
                        <React.Fragment key={image.cameraId}>
                            {colIndex > 0 && (
                                <ResizeHandle direction="horizontal" theme={theme}/>
                            )}
                            <Panel defaultSize={100 / rowCameras.length}>
                                <CameraCanvasPanel
                                    cameraImageData={image}
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
                    <ResizeHandle key={`row-handle-${r}`} direction="vertical" theme={theme}/>
                );
            }
        }

        return rows;
    }, [sortedCameraImageDataArray, initialLayout, theme, getCanvasRef]);

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
            {sortedCameraImageDataArray.length === 0 ? (
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
                <PanelGroup direction="vertical" style={{height: '100%'}}>
                    {panelStructure}
                </PanelGroup>
            )}
        </Box>
    );
};

// Memoize the entire CameraGridDisplay component to prevent unnecessary re-renders
export const ResizableCameraGridDisplay: React.FC = React.memo(() => {
    const {latestImageData} = useWebSocketContext();
    const hasImages = Object.keys(latestImageData).length > 0;



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
            { !hasImages ? (
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                    }}
                >
                    no images available
                </Box>
            ) : (
                <Box
                    sx={{
                        flexGrow: 1,
                        width: '100%',
                        overflow: 'hidden',
                    }}
                >
                    <CameraCanvasGridPanel/>
                </Box>
            )}
        </Box>
    );
});
