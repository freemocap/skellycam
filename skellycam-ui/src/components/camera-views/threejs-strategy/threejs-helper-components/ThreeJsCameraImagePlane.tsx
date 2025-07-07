import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { Html, useTexture } from "@react-three/drei";
import { ImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

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
    const textureRef = useRef<THREE.Texture | null>(null);
    const textureLoader = useRef(new THREE.TextureLoader());
    const [textureUrl, setTextureUrl] = useState<string | null>(null);

    // Update the texture URL when imageData changes
    useEffect(() => {
        if (imageData?.url && imageData.url !== textureUrl) {
            setTextureUrl(imageData.url);
        }
    }, [imageData, textureUrl]);

    // Load and update texture when URL changes
    useEffect(() => {
        if (!textureUrl) return;

        // Dispose previous texture to prevent memory leaks
        if (textureRef.current) {
            textureRef.current.dispose();
        }

        // Load the new texture
        textureLoader.current.load(
            textureUrl,
            (loadedTexture) => {
                // Configure texture settings
                loadedTexture.minFilter = THREE.LinearFilter;
                loadedTexture.magFilter = THREE.LinearFilter;
                loadedTexture.generateMipmaps = false;
                loadedTexture.flipY = true;
                loadedTexture.needsUpdate = true;

                // Store the texture reference
                textureRef.current = loadedTexture;

                // Update the material's map if mesh exists
                if (meshRef.current && meshRef.current.material) {
                    (meshRef.current.material as THREE.MeshBasicMaterial).map = loadedTexture;
                    (meshRef.current.material as THREE.MeshBasicMaterial).needsUpdate = true;
                }
            },
            undefined,
            (error) => {
                console.error(`Error loading texture for camera ${imageData.cameraId}:`, error);
            }
        );


    }, [textureUrl]);

    // Final cleanup when component unmounts
    useEffect(() => {
        return () => {
            if (textureRef.current) {
                textureRef.current.dispose();
                textureRef.current = null;
            }
        };
    }, []);

    return (
        <group position={position}>
            <mesh
                ref={meshRef}
                scale={[scale[0], scale[1], scale[2]]}
            >
                <planeGeometry />
                <meshBasicMaterial
                    color={textureRef.current ? undefined : "gray"}
                    transparent={true}
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
