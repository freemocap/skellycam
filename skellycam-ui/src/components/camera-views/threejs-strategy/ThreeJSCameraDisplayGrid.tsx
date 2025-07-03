import React, {Suspense, useEffect, useState} from 'react';
import {Canvas} from '@react-three/fiber';
import {Box, CircularProgress, Typography, useTheme} from '@mui/material';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {ThreeJSScene} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJSScene";
import {PlaceholderImage} from "@/components/camera-views/threejs-strategy/threejs-helper-components/PlaceholderImage";
import {LoadingIndicator} from "@/components/camera-views/threejs-strategy/threejs-helper-components/LoadingIndicator";


const ThreeJSCameraDisplayGrid: React.FC = () => {
    const theme = useTheme();
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
                <Canvas>
                    <Suspense fallback={<LoadingIndicator />}>
                        <PlaceholderImage />
                    </Suspense>
                </Canvas>
            ) : (
                <Canvas
                    gl={{
                        antialias: true,
                        alpha: true,
                        powerPreference: 'high-performance',
                        stencil: false,
                        depth: false
                    }}
                >
                    <ThreeJSScene />
                </Canvas>
            )}
        </Box>
    );
};

export default ThreeJSCameraDisplayGrid;
