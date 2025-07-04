import React, {useMemo} from "react";
import * as THREE from "three";
import {LinearFilter} from "three";
import {Html} from "@react-three/drei";

interface ProcessedImageInfo {
    cameraId: string;
    aspectRatio: number; // width / height
    cameraIndex: number; // Added camera index for sorting
}

export function ThreeJsCameraImagePlane({
                                            image,
                                            position,
                                            scale,
                                            cameraConfigs,
                                            bitmap
                                        }: {
    image: ProcessedImageInfo;
    position: [number, number, number];
    scale: [number, number, number];
    cameraConfigs: Record<string, any>;
    bitmap: ImageBitmap;
}) {
    const texture = useMemo(() => {
        // Create a default placeholder texture
        const createPlaceholder = (color = 'gray') => {
            const canvas = document.createElement('canvas');
            canvas.width = 2; // Use 2x2 instead of 1x1 to avoid some WebGL warnings
            canvas.height = 2;
            const ctx = canvas.getContext('2d');
            if (ctx) {
                ctx.fillStyle = color;
                ctx.fillRect(0, 0, 2, 2);
            }
            const tex = new THREE.CanvasTexture(canvas);
            tex.needsUpdate = true;
            return tex;
        };

        // Validate bitmap dimensions and state before creating texture
        if (!bitmap ||
            bitmap.width <= 0 ||
            bitmap.height <= 0 ||
            bitmap.width === undefined ||
            bitmap.height === undefined) {
            console.warn(`Invalid bitmap dimensions for camera ${image.cameraId}: ${bitmap?.width}x${bitmap?.height}`);
            return createPlaceholder('gray');
        }

        try {
            // Create a copy of the bitmap to prevent detachment issues
            const canvas = document.createElement('canvas');
            canvas.width = bitmap.width;
            canvas.height = bitmap.height;
            const ctx = canvas.getContext('2d');

            if (ctx) {
                try {
                    // Draw the bitmap to the canvas
                    ctx.drawImage(bitmap, 0, 0);

                    // Create texture from the canvas instead of directly from bitmap
                    const tex = new THREE.CanvasTexture(canvas);
                    tex.needsUpdate = true;
                    tex.minFilter = LinearFilter;
                    tex.generateMipmaps = false;
                    tex.flipY = false;
                    return tex;
                } catch (e) {
                    console.warn(`Bitmap for camera ${image.cameraId} appears to be detached:`, e);
                    return createPlaceholder('red');
                }
            }

            return createPlaceholder('blue');
        } catch (e) {
            console.error(`Error creating texture for camera ${image.cameraId}:`, e);
            return createPlaceholder('purple');
        }
    }, [bitmap, image.cameraId]);
    return (
        <group position={position}>
            <mesh scale={[scale[0], -scale[1], scale[2]]}>
                <planeGeometry/>
                <meshBasicMaterial map={texture}/>
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
                Camera {image.cameraIndex} ({image.cameraId})
            </Html>
        </group>
    );
}
