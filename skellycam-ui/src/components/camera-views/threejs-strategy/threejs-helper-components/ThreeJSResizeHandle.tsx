import React, { useState } from "react";
import { useThree } from "@react-three/fiber";
import * as THREE from "three";
import { Html } from "@react-three/drei";

interface ThreeJSResizeHandleProps {
    direction: "horizontal" | "vertical";
    position: [number, number, number];
    length: number;
    thickness: number;
    onDragStart: () => void;
    onDrag: (delta: number) => void;
    onDragEnd: () => void;
}

export function ThreeJSResizeHandle({
                                        direction,
                                        position,
                                        length,
                                        thickness = 0.05,
                                        onDragStart,
                                        onDrag,
                                        onDragEnd
                                    }: ThreeJSResizeHandleProps) {
    const [hovered, setHovered] = useState(false);
    const { camera } = useThree();

    // Calculate dimensions based on direction
    const width = direction === "vertical" ? length : thickness;
    const height = direction === "horizontal" ? length : thickness;
    // Create a larger hit area for easier interaction
    const hitAreaWidth = direction === "vertical" ? length : Math.max(thickness * 3, 0.15);
    const hitAreaHeight = direction === "horizontal" ? length : Math.max(thickness * 3, 0.15);
    // Track mouse position for dragging
    const handlePointerDown = (e: THREE.Event) => {
        onDragStart();

        // Store initial position
        const startPosition = (e as any).point.clone();
        let isCurrentlyDragging = true;

        // Handle pointer move
        const handlePointerMove = (e: MouseEvent) => {
            if (!isCurrentlyDragging) return;

            // Convert screen coordinates to world coordinates
            const mouse = new THREE.Vector2(
                (e.clientX / window.innerWidth) * 2 - 1,
                -(e.clientY / window.innerHeight) * 2 + 1
            );

            const raycaster = new THREE.Raycaster();
            raycaster.setFromCamera(mouse, camera);

            // Calculate plane for intersection
            const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
            const currentPoint = new THREE.Vector3();
            raycaster.ray.intersectPlane(plane, currentPoint);

            // Calculate delta based on direction
            const delta = direction === "horizontal"
                ? currentPoint.x - startPosition.x
                : currentPoint.y - startPosition.y;

            onDrag(delta);
        };

        // Handle pointer up
        const handlePointerUp = () => {
            isCurrentlyDragging = false;
            onDragEnd();

            window.removeEventListener("pointermove", handlePointerMove);
            window.removeEventListener("pointerup", handlePointerUp);
        };

        window.addEventListener("pointermove", handlePointerMove);
        window.addEventListener("pointerup", handlePointerUp);
    };

    return (
        <group position={position}>
            {/* Invisible hit area for easier interaction */}
            <mesh
                onPointerOver={() => setHovered(true)}
                onPointerOut={() => setHovered(false)}
                onPointerDown={handlePointerDown}
            >
                <planeGeometry args={[hitAreaWidth, hitAreaHeight]} />
                <meshBasicMaterial transparent={true} opacity={0} />
            </mesh>
            <mesh
                onPointerOver={() => setHovered(true)}
                onPointerOut={() => setHovered(false)}
                onPointerDown={handlePointerDown}
            >
                <planeGeometry args={[width, height]} />
                <meshBasicMaterial
                    color={hovered ? "#4f83cc" : "#2c5282"}
                    transparent={true}
                    opacity={hovered ? 0.8 : 0.5}
                />
            </mesh>
            {hovered && (
                <Html>
                    <div style={{
                        cursor: direction === "horizontal" ? "col-resize" : "row-resize",
                        position: "absolute",
                        width: "100%",
                        height: "100%"
                    }} />
                </Html>
            )}
        </group>
    );
}
