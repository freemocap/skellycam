// Placeholder Image when no cameras are connected
import {useLoader, useThree} from "@react-three/fiber";
import {TextureLoader} from "three";
import React from "react";

export function PlaceholderImage() {
    const texture = useLoader(TextureLoader, '/skellycam-logo.png');
    const {viewport} = useThree();

    // Calculate dimensions to fit the viewport while maintaining aspect ratio
    const aspectRatio = texture.image ? texture.image.width / texture.image.height : 1;
    let width, height;

    if (aspectRatio > viewport.width / viewport.height) {
        width = Math.min(4, viewport.width * 0.8);
        height = width / aspectRatio;
    } else {
        height = Math.min(4, viewport.height * 0.8);
        width = height * aspectRatio;
    }

    return (
        <mesh>
            <planeGeometry args={[width, height]}/>
            <meshBasicMaterial map={texture} transparent/>
        </mesh>
    );
}
