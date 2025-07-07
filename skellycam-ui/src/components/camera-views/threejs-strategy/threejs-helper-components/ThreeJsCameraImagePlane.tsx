import React, {useEffect, useRef, useState} from "react";
import * as THREE from "three";
import {Html} from "@react-three/drei";
import {ImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

export function ThreeJsCameraImagePlane({
                                            imageData,
                                            position,
                                            scale,
                                        }: {
    position: [number, number, number];
    scale: [number, number, number];
    imageData: ImageData;
}) {
    const meshRef = useRef<THREE.Mesh>(null);
    const [isLoaded, setIsLoaded] = useState(false);
    const [texture, setTexture] = useState<THREE.Texture | null>(null);

    // Create and configure the texture when component mounts
    useEffect(() => {
        const newTexture = new THREE.Texture();
        newTexture.minFilter = THREE.LinearFilter;
        newTexture.magFilter = THREE.LinearFilter;
        newTexture.generateMipmaps = false;
        newTexture.flipY = true; // Important for correct orientation
        setTexture(newTexture);

        // Clean up when component unmounts
        return () => {
            if (newTexture) {
                newTexture.dispose();
            }
        };
    }, []);

    // Update the texture when imageData changes
    useEffect(() => {
        if (!texture || !imageData || !imageData.url) {
            setIsLoaded(false);
            return;
        }

        const img = new Image();
        img.crossOrigin = "anonymous";

        img.onload = () => {
            if (texture) {
                texture.image = img;
                texture.needsUpdate = true; // Critical for updating the texture
                setIsLoaded(true);
            }
        };

        img.onerror = (e) => {
            console.error(`Error loading image for camera ${imageData.cameraId}:`, e);
            setIsLoaded(false);
        };

        img.src = imageData.url;
    }, [imageData, texture]);

    return (
        <group position={position}>
            <mesh
                ref={meshRef}
                scale={[scale[0], -scale[1], scale[2]]}
            >
                <planeGeometry />
                <meshBasicMaterial
                    map={texture}
                    transparent={true}
                    opacity={isLoaded ? 1 : 0.5}
                />
            </mesh>
            <Html
                position={[
                    -scale[0] / 2 + 0.05,
                    scale[1] / 2 - 0.05,
                    0.1
                ]}
                style={{
                    backgroundColor: 'rgba(0,0,0,0.5)',
                    color: 'white',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '0.8rem',
                    whiteSpace: 'nowrap',
                }}
            >
                Camera {imageData?.cameraIndex} ({imageData?.cameraId}) Frame# {imageData?.frameNumber}
                {imageData?.imageWidth && imageData?.imageHeight && (
                    <span> - {imageData.imageWidth}x{imageData.imageHeight}</span>
                )}
            </Html>
        </group>
    );
}
