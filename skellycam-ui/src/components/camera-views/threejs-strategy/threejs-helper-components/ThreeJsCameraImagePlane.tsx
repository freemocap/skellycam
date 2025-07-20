import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import { Html } from "@react-three/drei";
import { ImageData } from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";
import { useWebSocketContext } from "@/context/websocket-context/WebSocketContext";

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
  const materialRef = useRef<THREE.MeshBasicMaterial | null>(null);

  // Get the sendFrameAcknowledgment function from context
  const { sendFrameAcknowledgment } = useWebSocketContext();
  // Create texture and material only once
  useEffect(() => {
    // Create a texture that we'll reuse
    const texture = new THREE.Texture();
    texture.minFilter = THREE.NearestFilter;
    texture.magFilter = THREE.NearestFilter;
    texture.generateMipmaps = false;
    texture.flipY = true;
    textureRef.current = texture;

    // Create material that references this texture
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
    });
    materialRef.current = material;

    // Apply to mesh if it exists
    if (meshRef.current) {
      meshRef.current.material = material;
    }

    // Cleanup on unmount
    return () => {
      if (texture) texture.dispose();
      if (material) material.dispose();
    };
  }, []);

// Update texture when new JPEG data arrives
useEffect(() => {
  if (!imageData?.jpegData || !textureRef.current || !materialRef.current)
    return;

  // Create a temporary blob from the JPEG data
  const blob = new Blob([imageData.jpegData], { type: "image/jpeg" });
  
  // Use createImageBitmap instead of URL.createObjectURL
  createImageBitmap(blob)
    .then(imageBitmap => {
      // Update our reused texture with the new image
      if (textureRef.current) {
        textureRef.current.image = imageBitmap;
        textureRef.current.needsUpdate = true;

        // Ensure material is using the texture
        if (materialRef.current) {
          materialRef.current.map = textureRef.current;
          materialRef.current.transparent = false;
          materialRef.current.needsUpdate = true;
        }
        
        // Send acknowledgment after texture is updated
        sendFrameAcknowledgment(imageData.cameraId, imageData.frameNumber);
      }
    })
    .catch(error => {
      console.error(
        `Error loading image for camera ${imageData.cameraId}:`,
        error
      );
    });
  }, [imageData?.jpegData, sendFrameAcknowledgment, imageData?.cameraId, imageData?.frameNumber]);

  return (
    <group position={position}>
      <mesh ref={meshRef} scale={[scale[0], scale[1], scale[2]]}>
        <planeGeometry />
        {/* Material will be set by the useEffect */}
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
