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
        // Validate bitmap dimensions before creating texture
        if (!bitmap || bitmap.width <= 0 || bitmap.height <= 0) {
            console.warn(`Invalid bitmap dimensions for camera ${image.cameraId}: ${bitmap?.width}x${bitmap?.height}`);
            // Return a small placeholder texture instead
            const canvas = document.createElement('canvas');
            canvas.width = 1;
            canvas.height = 1;
            const ctx = canvas.getContext('2d');
            if (ctx) {
                ctx.fillStyle = 'gray';
                ctx.fillRect(0, 0, 1, 1);
            }
            const tex = new THREE.CanvasTexture(canvas);
            tex.needsUpdate = true;
            return tex;
        }
        const tex = new THREE.Texture(bitmap);
        tex.needsUpdate = true;
        tex.minFilter = LinearFilter;
        tex.generateMipmaps = false;
        tex.flipY = false;
        return tex;
    }, [bitmap]);

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
                Camera {cameraConfigs[image.cameraId]?.camera_index ?? '?'} ({image.cameraId})
            </Html>
        </group>
    );
}
