import React, {useCallback, useEffect, useMemo, useRef} from 'react';
import {Box, Paper, Typography, useTheme} from '@mui/material';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {Panel, PanelGroup, PanelResizeHandle} from "react-resizable-panels";
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {useCameraGridLayout} from "@/hooks/useCameraGridLayout";


const CameraCanvasPanel = React.memo(({
                                          cameraImageData,
                                          canvasRef
                                      }: {
    cameraImageData: CameraImageData;
    canvasRef: (el: HTMLCanvasElement | null) => void;
}) => {

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

const CameraCanvasGridPanel: React.FC = (
    {latestImageData}: { latestImageData: Record<string, CameraImageData> }
) => {
    const theme = useTheme();

    const canvasContextRefs = useRef<Record<string, CanvasRenderingContext2D | null>>({});


    // Refs for container and canvases
    const containerRef = useRef<HTMLDivElement>(null);
    const canvasRefs = useRef<Record<string, HTMLCanvasElement | null>>({});

    const initialLayout = useCameraGridLayout(latestImageData,
        containerRef.current?.clientWidth,
        containerRef.current?.clientHeight);
    // Calculate optimal grid layout
    useEffect(() => {
        // Use requestAnimationFrame to batch canvas updates
        Object.entries(latestImageData).forEach(([cameraId, cameraImageData]) => {
            const canvas = canvasRefs.current[cameraId];
            if (canvas) {
                if (!canvasContextRefs.current[cameraId]) {
                    canvasContextRefs.current[cameraId] = canvas.getContext('2d', {alpha: false});
                }
                const ctx = canvasContextRefs.current[cameraId];
                if (ctx) {
                    if (canvas.width !== cameraImageData.imageWidth || canvas.height !== cameraImageData.imageHeight) {
                        canvas.width = cameraImageData.imageWidth;
                        canvas.height = cameraImageData.imageHeight;
                    }
                    // Draw the bitmap
                    if (cameraImageData.imageBitmap) {
                    ctx.drawImage(cameraImageData.imageBitmap, 0, 0);
                    }
                }
            }
        });


    }, [latestImageData]);


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
    }, [canvasRefs, initialLayout, theme]);

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
            {!hasImages ? (
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
                    <CameraCanvasGridPanel latestImageData={latestImageData}/>
                </Box>
            )}
        </Box>
    );
});
