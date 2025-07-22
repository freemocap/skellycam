import React, {useEffect, useRef} from "react";
import * as THREE from "three";
import {Html} from "@react-three/drei";
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import {useWebSocketContext} from "@/context/websocket-context/WebSocketContext";

export function ThreeJsCameraImagePlane({
                                            imageData,
                                            position,
                                            scale,
                                        }: {
    position: [number, number, number];
    scale: [number, number, number];
    imageData: CameraImageData;
}) {
    const meshRef = useRef<THREE.Mesh>(null);
    const textureRef = useRef<THREE.VideoFrameTexture | null>(null);
    const materialRef = useRef<THREE.MeshBasicMaterial | null>(null);
    const{registerCameraViewTexture} = useWebSocketContext();


    // Create (or recreate) texture and material when the ImageData (i.e. scale) changes
    useEffect(() => {
        console.log(`Creating texture for camera ${imageData.cameraId} at position ${position} with scale ${scale}`);
        const texture = new THREE.VideoFrameTexture();
        texture.minFilter = THREE.NearestFilter;
        texture.magFilter = THREE.NearestFilter;
        texture.generateMipmaps = false;
        textureRef.current = texture;

        // Create material that references this texture
        const material = new THREE.MeshBasicMaterial({
            map: texture,
        });
        materialRef.current = material;

        // Apply to mesh if it exists
        if (meshRef.current) {
            meshRef.current.material = material;
        }
        registerCameraViewTexture(imageData.cameraId, texture);
    }, [ textureRef, materialRef, registerCameraViewTexture , imageData.cameraId]);



    return (
        <group position={position}>
            <mesh ref={meshRef} scale={[scale[0], scale[1], scale[2]]}>
                <planeGeometry/>
                {/* Material and texture will be set by the useEffect */}
            </mesh>
            <Html
                position={[-scale[0] / 2 + 0.05, scale[1] / 2 - 0.05, 0.1]}
                style={{
                    backgroundColor: "rgba(0,0,0,0.5)",
                    color: "white",
                    padding: "2px 8px",
                    borderRadius: "4px",
                    fontSize: "0.8rem",
                    whiteSpace: "nowrap",
                }}
            >
                Camera {imageData?.cameraIndex} ({imageData?.cameraId}) Frame#{" "}
                {imageData?.frameNumber}
            </Html>
        </group>
    );
}
