import React, {Suspense, useEffect, useState} from 'react';
import {Canvas} from '@react-three/fiber';
import {Box, CircularProgress, Typography, useTheme} from '@mui/material';
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {ThreeJSScene} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJSScene";
import {PlaceholderImage} from "@/components/camera-views/threejs-strategy/threejs-helper-components/PlaceholderImage";
import {LoadingIndicator} from "@/components/camera-views/threejs-strategy/threejs-helper-components/LoadingIndicator";


const ThreeJSCameraDisplayGrid: React.FC = () => {
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
