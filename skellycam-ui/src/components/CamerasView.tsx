// skellycam-ui/src/components/CamerasView.tsx
import { Box, Typography } from "@mui/material";
import React, { useEffect, useState, useRef, useMemo, useCallback } from "react";
import { useLatestImagesContext } from "@/context/latest-images-context/LatestImagesContext";
import { RowsPhotoAlbum } from "react-photo-album";
import "react-photo-album/rows.css";
import { useAppSelector } from "@/store/AppStateStore";

interface CameraImage {
    src: string;
    width: number;
    height: number;
    key?: string;
    alt?: string;
}

// Default dimensions as fallback
const DEFAULT_WIDTH = 640;
const DEFAULT_HEIGHT = 480;

export const CamerasView = () => {
    const { latestImageUrls } = useLatestImagesContext();
    const [cameraImages, setCameraImages] = useState<CameraImage[]>([]);
    const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
    const containerRef = useRef<HTMLDivElement>(null);
    const cameraConfigs = useAppSelector(state => state.latestPayload.cameraConfigs);

    // Persistent dimension cache that survives across renders
    const dimensionCache = useRef<Record<string, { width: number, height: number }>>({});

    // Track which camera IDs we've already processed to avoid redundant loading
    const processedCameraIds = useRef<Set<string>>(new Set());

    // Setup resize observer to track container dimensions
    useEffect(() => {
        if (!containerRef.current) return;

        const resizeObserver = new ResizeObserver(entries => {
            const { width, height } = entries[0].contentRect;
            setContainerSize({ width, height });
        });

        resizeObserver.observe(containerRef.current);
        return () => resizeObserver.disconnect();
    }, []);

    // Only reset dimension cache when camera configs change
    useEffect(() => {
        if (!cameraConfigs) return;

        // Check if we have new cameras that aren't in our dimension cache
        const currentCameraIds = new Set(Object.keys(dimensionCache.current));
        const newCameraIds = new Set(Object.keys(cameraConfigs));

        // Only clear cache if camera IDs have changed
        const hasNewCameras = Array.from(newCameraIds).some(id => !currentCameraIds.has(id));
        const hasRemovedCameras = Array.from(currentCameraIds).some(id => !newCameraIds.has(id));

        if (hasNewCameras || hasRemovedCameras) {
            dimensionCache.current = {};
            processedCameraIds.current.clear();
        }
    }, [cameraConfigs]);

    // Process individual image once loaded - extracted as memoized callback
    const processImage = useCallback((cameraId: string, imageUrl: string): Promise<CameraImage> => {
        // Use cached dimensions if available
        if (dimensionCache.current[cameraId]) {
            const { width, height } = dimensionCache.current[cameraId];
            return Promise.resolve({
                src: imageUrl,
                width,
                height,
                key: cameraId,
                alt: `Camera ${cameraId}`
            });
        }

        // Otherwise load the image to get dimensions
        return new Promise<CameraImage>(resolve => {
            const img = new Image();

            img.onload = () => {
                const dimensions = {
                    width: img.naturalWidth,
                    height: img.naturalHeight
                };
                dimensionCache.current[cameraId] = dimensions;

                resolve({
                    src: imageUrl,
                    ...dimensions,
                    key: cameraId,
                    alt: `Camera ${cameraId}`
                });
            };

            img.onerror = () => {
                dimensionCache.current[cameraId] = {
                    width: DEFAULT_WIDTH,
                    height: DEFAULT_HEIGHT
                };

                resolve({
                    src: imageUrl,
                    width: DEFAULT_WIDTH,
                    height: DEFAULT_HEIGHT,
                    key: cameraId,
                    alt: `Camera ${cameraId}`
                });
            };

            img.src = imageUrl;
        });
    }, []);

// Load and process camera images - optimized for frequent updates
    useEffect(() => {
        if (!latestImageUrls) return;

        const currentCameraIds = new Set(Object.keys(latestImageUrls));

        // Fast path: dimensions are already cached for all cameras
        const allCamerasDimensionsCached = Object.keys(latestImageUrls).every(
            id => dimensionCache.current[id]
        );

        if (allCamerasDimensionsCached) {
            // Just update URLs without re-measuring
            setCameraImages(prevImages => {
                // Create new array only if URLs have changed
                const needsUpdate = prevImages.some(img =>
                    img.key && latestImageUrls[img.key] !== img.src
                );

                if (!needsUpdate) return prevImages;

                // Update just the image URLs, maintain same objects otherwise
                const updatedImages = prevImages.map(img => {
                    if (img.key && latestImageUrls[img.key] !== img.src) {
                        return { ...img, src: latestImageUrls[img.key] };
                    }
                    return img;
                });

                // Add any new cameras
                const existingIds = new Set(updatedImages.map(img => img.key));
                const newImages = Object.entries(latestImageUrls)
                    .filter(([id]) => !existingIds.has(id))
                    .map(([id, url]) => ({
                        src: url,
                        width: dimensionCache.current[id]?.width || DEFAULT_WIDTH,
                        height: dimensionCache.current[id]?.height || DEFAULT_HEIGHT,
                        key: id,
                        alt: `Camera ${id}`
                    }));

                // Filter out removed cameras and add new ones
                return [
                    ...updatedImages.filter(img => img.key && currentCameraIds.has(img.key)),
                    ...newImages
                ];
            });
            return;
        }

        // Slow path: need to measure dimensions for some cameras
        const measureCameras = async () => {
            const camerasToMeasure = Object.entries(latestImageUrls)
                .filter(([id]) => !dimensionCache.current[id]);

            if (camerasToMeasure.length === 0) return;

            const newPhotos = await Promise.all(
                camerasToMeasure.map(([cameraId, imageUrl]) =>
                    processImage(cameraId, imageUrl)
                )
            );

            // Update with newly measured photos
            setCameraImages(prevPhotos => {
                const updatedPhotos = [...prevPhotos];

                // Update or add new photos
                newPhotos.forEach(newPhoto => {
                    const index = updatedPhotos.findIndex(p => p.key === newPhoto.key);
                    if (index >= 0) {
                        updatedPhotos[index] = newPhoto;
                    } else {
                        updatedPhotos.push(newPhoto);
                    }
                });

                // Also update URLs for any other cameras
                updatedPhotos.forEach(photo => {
                    if (photo.key && latestImageUrls[photo.key] !== photo.src) {
                        photo.src = latestImageUrls[photo.key];
                    }
                });

                // Remove photos that no longer exist
                return updatedPhotos.filter(photo =>
                    photo.key && currentCameraIds.has(photo.key)
                );
            });
        };

        measureCameras();
    }, [latestImageUrls, processImage]);
    // Calculate layout parameters based on container size and photo count
    const layoutConfig = useMemo(() => {
        if (!containerSize.width || !containerSize.height || !cameraImages.length) {
            return {
                targetRowHeight: 300,
                maxPhotosPerRow: 3
            };
        }

        const cameraCount = cameraImages.length;
        const containerAspect = containerSize.width / containerSize.height;

        // Calculate optimal number of rows based on container aspect ratio and photo count
        const optimalRows = Math.max(
            1,
            Math.min(
                Math.ceil(Math.sqrt(cameraCount / containerAspect)),
                cameraCount
            )
        );

        // Calculate the maximum photos per row to force a good distribution
        const optimalPhotosPerRow = Math.ceil(cameraCount / optimalRows);

        // Calculate target row height with safety margin
        const safeHeight = containerSize.height - 40; // 40px safety margin
        const rowHeight = Math.floor(safeHeight / optimalRows);

        return {
            targetRowHeight: Math.max(150, rowHeight),
            maxPhotosPerRow: optimalPhotosPerRow
        };
    }, [cameraImages.length, containerSize.width, containerSize.height]);

    // Memoize the cameraImage renderer to prevent recreating on every render
    const renderCameraImage = useCallback(({ cameraImage, imageProps, wrapperStyle }) => (
        <div style={{
            ...wrapperStyle,
            position: 'relative',
            marginBottom: '5px'
        }}>
            <img
                {...imageProps}
                style={{
                    ...imageProps.style,
                    objectFit: 'contain',
                    border: '1px solid rgba(0,0,0,0.1)',
                    borderRadius: '4px',
                    maxHeight: '100%'
                }}
            />
            {cameraImage.key && (
                <div style={{
                    position: 'absolute',
                    bottom: 0,
                    left: 0,
                    backgroundColor: 'rgba(0,0,0,0.5)',
                    color: 'white',
                    padding: '4px 8px',
                    fontSize: '14px',
                    borderRadius: '0 4px 0 0'
                }}>
                    Camera {cameraImage.key}
                </div>
            )}
        </div>
    ), []);

    if (!latestImageUrls || Object.keys(latestImageUrls).length === 0) {
        return (
            <Box sx={{ p: 2 }}>
                <Typography variant="h6" color="secondary">
                    Waiting for cameras to connect...
                </Typography>
            </Box>
        );
    }

    return (
        <Box
            ref={containerRef}
            sx={{
                display: "flex",
                flexDirection: "column",
                height: "100%",
                width: "100%",
                overflow: "hidden",
                padding: 2
            }}
        >
            {cameraImages.length > 0 && (
                <RowsPhotoAlbum
                    photos={cameraImages}
                    layout="rows"
                    spacing={8}
                    targetRowHeight={layoutConfig.targetRowHeight}
                    rowConstraints={{
                        minPhotos: 1,
                        maxPhotos: layoutConfig.maxPhotosPerRow
                    }}
                    layoutOptions={{
                        padding: { top: 10, right: 10, bottom: 10, left: 10 }
                    }}
                    renderPhoto={renderCameraImage}
                />
            )}
        </Box>
    );
};
