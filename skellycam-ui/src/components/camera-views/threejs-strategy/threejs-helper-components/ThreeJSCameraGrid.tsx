// Camera Grid component
import {ProcessedImageInfo, useCameraGridLayout} from "@/hooks/useCameraGridLayout";
import {useThree} from "@react-three/fiber";
import React, {useMemo} from "react";
import {ThreeJsCameraImagePlane} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJsCameraImagePlane";

export function ThreeJSCameraGrid({
                                      images,
                                      cameraConfigs,
                                      bitmaps
                                  }: {
    images: ProcessedImageInfo[];
    cameraConfigs: Record<string, any>;
    bitmaps: Record<string, ImageBitmap>;
}) {
    const {viewport} = useThree();
    const layout = useCameraGridLayout(images, viewport.width, viewport.height);

    // Calculate grid positions and scales
    const gridItems = useMemo(() => {
        const items = [];
        const {rows, cols} = layout;
        const cellWidth = viewport.width / cols;
        const cellHeight = viewport.height / rows;

        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const index = r * cols + c;
                if (index >= images.length) continue;

                const image = images[index];
                const bitmap = bitmaps[image.cameraId];
                if (!bitmap) continue;

                // Calculate position in grid (centered in cell)
                const x = -viewport.width / 2 + cellWidth * (c + 0.5);
                const y = viewport.height / 2 - cellHeight * (r + 0.5);

                // Calculate scale to fit in cell while maintaining aspect ratio
                const maxWidth = cellWidth * 0.95;
                const maxHeight = cellHeight * 0.95;
                let width, height;

                if (image.aspectRatio > maxWidth / maxHeight) {
                    width = maxWidth;
                    height = width / image.aspectRatio;
                } else {
                    height = maxHeight;
                    width = height * image.aspectRatio;
                }

                items.push({
                    image,
                    position: [x, y, 0] as [number, number, number],
                    scale: [width, height, 1] as [number, number, number],
                    bitmap
                });
            }
        }

        return items;
    }, [images, layout, viewport.width, viewport.height, bitmaps]);

    return (
        <>
            {gridItems.map((item, index) => (
                <ThreeJsCameraImagePlane
                    key={item.image.cameraId}
                    image={item.image}
                    position={item.position}
                    scale={item.scale}
                    cameraConfigs={cameraConfigs}
                    bitmap={item.bitmap}
                />
            ))}
        </>
    );
}
