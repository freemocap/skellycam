// Camera Grid component
import {useCameraGridLayout} from "@/hooks/useCameraGridLayout";
import {useThree} from "@react-three/fiber";
import React, {useEffect, useMemo} from "react";
import {
    ThreeJsCameraImagePlane
} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJsCameraImagePlane";
import {
    ThreeJSResizeHandle
} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJSResizeHandle";
import {
    useThreeJSGridResize
} from "@/components/camera-views/threejs-strategy/threejs-helper-components/ThreeJSGridResizeContext";
import {CameraImageData} from "@/context/websocket-context/useWebsocketBinaryMessageProcessor";

export interface CameraGridItem {
    position: [number, number, number];
    scale: [number, number, number];
    imageData: CameraImageData;
    cell: {
        row: number;
        column: number;
        x: number;
        y: number;
        width: number;
        height: number;
    };
}

export function ThreeJSCameraGrid({
                                      imageData,
                                      sendFrameAcknowledgment
                                  }: {
    imageData: Record<string, CameraImageData>;
    sendFrameAcknowledgment: (cameraId: string, frameNumber: number) => void;
}) {
    const {viewport} = useThree();
    const layout = useCameraGridLayout(imageData, viewport.width, viewport.height);
    const {gridCells, initializeGrid, startResizing, updateResize, endResizing} = useThreeJSGridResize();

    // Initialize grid cells based on layout
    useEffect(() => {
        if (layout.rows > 0 && layout.columns > 0) {
            initializeGrid(layout.rows, layout.columns);
        }
    }, [layout.rows, layout.columns, initializeGrid]);


    // Calculate grid positions and scales
    const cameraGridItems: CameraGridItem[] = useMemo(() => {
        const imageDataArray: CameraImageData[] = Object.values(imageData);
        if (gridCells.length === 0 || imageDataArray.length === 0) return [];

        const gridItems: CameraGridItem[] = [];
        const {rows, columns} = layout;

        for (let row = 0; row < rows; row++) {
            for (let column = 0; column < columns; column++) {
                const index = row * columns + column;
                if (index >= imageDataArray.length) continue;

                // Get the camera data for this grid position
                const cameraImageData = imageDataArray[index];
                if (!cameraImageData) continue;

                // Find the corresponding grid cell
                const cell = gridCells.find(cell => cell.row === row && cell.column === column);
                if (!cell) continue;

                // Calculate position in grid (centered in cell)
                const cellWidth = cell.width * viewport.width;
                const cellHeight = cell.height * viewport.height;
                const x = -viewport.width / 2 + (cell.x * viewport.width) + (cellWidth / 2);
                const y = viewport.height / 2 - (cell.y * viewport.height) - (cellHeight / 2);

                // Calculate aspect ratio from image dimensions
                const aspectRatio = cameraImageData.imageBitmap.width / cameraImageData.imageBitmap.height;

                // Calculate scale to fit in cell while maintaining aspect ratio
                const maxWidth = cellWidth * 0.95;
                const maxHeight = cellHeight * 0.95;
                let width, height;

                if (aspectRatio > maxWidth / maxHeight) {
                    width = maxWidth;
                    height = width / aspectRatio;
                } else {
                    height = maxHeight;
                    width = height * aspectRatio;
                }

                gridItems.push({
                    position: [x, y, 0] as [number, number, number],
                    scale: [width, height, 1] as [number, number, number],
                    imageData: cameraImageData,
                    cell
                });
            }
        }

        return gridItems;
    }, [layout, viewport.width, viewport.height, imageData, gridCells]);
    // Generate resize handles
    const resizeHandles = useMemo(() => {
        if (gridCells.length === 0) return [];

        const handles = [];
        const {rows, columns} = layout;

        // Horizontal handles (between columns)
        for (let row = 0; row < rows; row++) {
            for (let column = 0; column < columns - 1; column++) {
                const leftCell = gridCells.find(cell => cell.row === row && cell.column === column);
                const rightCell = gridCells.find(cell => cell.row === row && cell.column === column + 1);

                if (leftCell && rightCell) {
                    const handleId = `h_row${row}_column${column}`;
                    const x = -viewport.width / 2 + (leftCell.x + leftCell.width) * viewport.width;
                    const y = viewport.height / 2 - (leftCell.y + leftCell.height / 2) * viewport.height;
                    const length = leftCell.height * viewport.height * 0.9;

                    handles.push({
                        id: handleId,
                        direction: "horizontal" as const,
                        position: [x, y, 1] as [number, number, number],
                        length: length,
                        thickness: 5,
                        onDragStart: () => startResizing(handleId),
                        onDrag: (delta: number) => updateResize(handleId, delta / viewport.width),
                        onDragEnd: endResizing
                    });
                }
            }
        }

        // Vertical handles (between rows)
        for (let column = 0; column < columns; column++) {
            for (let row = 0; row < rows - 1; row++) {
                const topCell = gridCells.find(cell => cell.row === row && cell.column === column);
                const bottomCell = gridCells.find(cell => cell.row === row + 1 && cell.column === column);

                if (topCell && bottomCell) {
                    const handleId = `v_row${row}_column${column}`;
                    const x = -viewport.width / 2 + (topCell.x + topCell.width / 2) * viewport.width;
                    const y = viewport.height / 2 - (topCell.y + topCell.height) * viewport.height;
                    const length = topCell.width * viewport.width * 0.9;

                    handles.push({
                        id: handleId,
                        direction: "vertical" as const,
                        position: [x, y, 1] as [number, number, number],
                        length: length,
                        thickness: 5,
                        onDragStart: () => startResizing(handleId),
                        onDrag: (delta: number) => updateResize(handleId, delta / viewport.height),
                        onDragEnd: endResizing
                    });
                }
            }
        }

        return handles;
    }, [gridCells, layout, viewport.width, viewport.height, startResizing, updateResize, endResizing]);


    return (
        <>
            {cameraGridItems.map((item, index) => (
                <ThreeJsCameraImagePlane
                    key={`camera-${item.imageData.cameraId}-${index}`}
                    position={item.position}
                    scale={item.scale}
                    imageData={item.imageData}
                    sendFrameAcknowledgment={sendFrameAcknowledgment}
                />
            ))}

            {resizeHandles.map(handle => (
                <ThreeJSResizeHandle
                    key={handle.id}
                    direction={handle.direction}
                    position={handle.position}
                    length={handle.length}
                    thickness={handle.thickness}
                    onDragStart={handle.onDragStart}
                    onDrag={handle.onDrag}
                    onDragEnd={handle.onDragEnd}
                />
            ))}
        </>
    );
}
