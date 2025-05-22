import React, {useEffect, useMemo, useRef, useState} from 'react';
import {Box, CircularProgress, Grid, Paper, Typography, useTheme} from '@mui/material';
import {useAppSelector} from '@/store/AppStateStore';
import {CameraConfigsSchema} from "@/store/slices/cameras-slices/camera-types";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

// Represents image data for a camera
interface ProcessedImageInfo {
    cameraId: string;
    aspectRatio: number; // width / height
}

const ImageGrid: React.FC = () => {
    const theme = useTheme();
    const {latestImageBitmaps} = useWebSocketContext();
    const latestPayload = useAppSelector(state => state.latestPayload);

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

    // Container dimensions for layout calculations
    const [containerDimensions, setContainerDimensions] = useState({width: 0, height: 0});

    // Calculate image info (just cameraId and aspectRatio) from bitmaps
    const processedImages = useMemo(() => {
        const images: Record<string, ProcessedImageInfo> = {};

        Object.entries(latestImageBitmaps).forEach(([cameraId, bitmap]) => {
            images[cameraId] = {
                cameraId,
                aspectRatio: bitmap.width / bitmap.height,
            };
        });

        return images;
    }, [latestImageBitmaps]);

    // Draw bitmaps to canvases whenever they change
    useEffect(() => {

        Object.entries(latestImageBitmaps).forEach(([cameraId, bitmap]) => {
            const canvas = canvasRefs.current[cameraId];
            if (canvas) {
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    // Set canvas dimensions to match bitmap
                    canvas.width = bitmap.width;
                    canvas.height = bitmap.height;

                    // Clear canvas and draw the bitmap
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(bitmap, 0, 0);
                }
            }
        });
    }, [latestImageBitmaps]);

    // Update container dimensions on resize
    useEffect(() => {
        const updateDimensions = () => {
            if (containerRef.current) {
                setContainerDimensions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight,
                });
            }
        };

        updateDimensions();
        const resizeObserver = new ResizeObserver(updateDimensions);

        if (containerRef.current) {
            resizeObserver.observe(containerRef.current);
        }

        return () => {
            if (containerRef.current) {
                resizeObserver.unobserve(containerRef.current);
            }
        };
    }, []);

    // Calculate optimal grid layout
    const {cols, rows} = useMemo(() => {
        const images = Object.values(processedImages);
        if (images.length === 0) return {cols: 1, rows: 1};

        // Find the grid configuration that maximizes image size
        let bestLayout = {cols: 1, rows: 1, area: 0};
        const containerWidth = containerDimensions.width || 1200;
        const containerHeight = containerDimensions.height || 800;

        // Try different grid configurations
        for (let cols = 1; cols <= images.length; cols++) {
            const rows = Math.ceil(images.length / cols);

            // Calculate the area each image would get
            const cellWidth = containerWidth / cols;
            const cellHeight = containerHeight / rows;

            // Calculate minimum scaling factor across all images
            let minScale = Infinity;
            images.forEach(image => {
                const scaleWidth = cellWidth / (image.aspectRatio * cellHeight);
                const scaleHeight = cellHeight / (image.aspectRatio === 0 ? 1 : cellWidth / image.aspectRatio);
                minScale = Math.min(minScale, Math.min(scaleWidth, scaleHeight));
            });

            // Calculate effective area
            const effectiveArea = minScale * (cellWidth * cellHeight);

            if (effectiveArea > bestLayout.area) {
                bestLayout = {cols, rows, area: effectiveArea};
            }
        }

        return {cols: bestLayout.cols, rows: bestLayout.rows};
    }, [processedImages, containerDimensions.width, containerDimensions.height]);


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
            {Object.keys(processedImages).length === 0 ? (
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
                <Grid
                    container
                    spacing={1}
                    sx={{
                        height: '100%',
                        width: '100%',
                        padding: 1,
                        boxSizing: 'border-box',
                    }}
                >
                    {Object.entries(processedImages).map(([cameraId, image]) => (
                        <Grid
                            item
                            key={cameraId}
                            xs={12 / cols}
                            sx={{
                                height: `${100 / rows}%`,
                                padding: '4px',
                                boxSizing: 'border-box',
                            }}
                        >
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
                                    Camera {cameraConfigs[cameraId]?.camera_index || '?'} ({cameraId})
                                </Box>
                                <Box
                                    sx={{
                                        height: '100%',
                                        width: '100%',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        overflow: 'hidden',
                                    }}
                                >
                                    <canvas
                                        ref={el => canvasRefs.current[cameraId] = el}
                                        style={{
                                            maxWidth: '100%',
                                            maxHeight: '100%',
                                            objectFit: 'contain',
                                        }}
                                    />
                                </Box>
                            </Paper>
                        </Grid>
                    ))}
                </Grid>
            )}
        </Box>
    );
};

const CameraGridDisplay: React.FC = () => {
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
};

export default CameraGridDisplay;
