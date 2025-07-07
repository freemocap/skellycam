// Main Scene component
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";
import React, {Suspense} from "react";
import {useThree} from "@react-three/fiber";
import {OrthographicCamera} from "@react-three/drei";
import {
    ThreeJSCameraGrid
} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJSCameraGrid";
import {PlaceholderImage} from "@/components/camera-views/threejs-strategy/threejs-helper-components/PlaceholderImage";
import {LoadingIndicator} from "@/components/camera-views/threejs-strategy/threejs-helper-components/LoadingIndicator";
import {useTheme} from "@mui/material/styles";
import {
    ThreeJSGridResizeProvider
} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJSGridResizeContext";

export function ThreeJSScene() {
    const theme = useTheme();
    const {latestImageData} = useWebSocketContext();




    const hasImages = latestImageData.length > 0;

    // Set up orthographic camera
    const {viewport} = useThree();

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
                <ThreeJSGridResizeProvider>
                    <ThreeJSCameraGrid
                        imageData={latestImageData}
                    />
                </ThreeJSGridResizeProvider>
            ) : (
                <Suspense fallback={<LoadingIndicator/>}>
                    <PlaceholderImage/>
                </Suspense>
            )}
        </>
    );
}
