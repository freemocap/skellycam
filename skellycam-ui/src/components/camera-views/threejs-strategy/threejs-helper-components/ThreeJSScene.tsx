// Main Scene component
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import {useAppSelector} from "@/store/AppStateStore";
import React, {Suspense, useEffect, useMemo} from "react";
import {CameraConfigsSchema} from "@/store/slices/cameras-slices/camera-types";
import {sortCamerasByIndex} from "@/hooks/useCameraGridLayout";
import {useThree} from "@react-three/fiber";
import {OrthographicCamera} from "@react-three/drei";
import {ThreeJSCameraGrid} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJSCameraGrid";
import {PlaceholderImage} from "@/components/camera-views/threejs-strategy/threejs-helper-components/PlaceholderImage";
import {LoadingIndicator} from "@/components/camera-views/threejs-strategy/threejs-helper-components/LoadingIndicator";
import {useTheme} from "@mui/material/styles";

export function ThreeJSScene() {
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

    // Calculate image info and sort by camera index
    const sortedProcessedImages = useMemo(() =>
            sortCamerasByIndex(latestImageBitmaps, cameraConfigs),
        [latestImageBitmaps, cameraConfigs]);

    const hasImages = sortedProcessedImages.length > 0;

    // Set up orthographic camera
    const {viewport} = useThree();

    useEffect(() => {
        // Update camera to fit viewport
    }, [viewport]);

    return (
        <>
            <OrthographicCamera
                makeDefault
                position={[0, 0, 10]}
                zoom={1}
                near={0.1}
                far={1000}
            />
            <color attach="background" args={[theme.palette.background.default]}/>

            {hasImages ? (
                <ThreeJSCameraGrid
                    images={sortedProcessedImages}
                    cameraConfigs={cameraConfigs}
                    bitmaps={latestImageBitmaps}
                />
            ) : (
                <Suspense fallback={<LoadingIndicator/>}>
                    <PlaceholderImage/>
                </Suspense>
            )}
        </>
    );
}
