import React, {useEffect, useRef, useState} from 'react';
import {Box, CircularProgress, Grid, Paper, Typography, useTheme} from '@mui/material';
import {useAppSelector} from '@/store/AppStateStore';
import {useLatestImagesContext} from '@/context/latest-images-context/LatestImagesContext';

// Represents image data for a camera
interface ImageData {
  src: string;
  cameraId: string;
  aspectRatio: number; // width / height
}

const ImageGrid: React.FC = () => {
  const theme = useTheme();
  const { latestImageUrls} = useLatestImagesContext();
  const cameraConfigs = useAppSelector(state => state.latestPayload.cameraConfigs);

  const [processedImages, setProcessedImages] = useState<ImageData[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerDimensions, setContainerDimensions] = useState({ width: 0, height: 0 });

  // Process the incoming images
  useEffect(() => {
    if (!latestImageUrls || Object.keys(latestImageUrls).length === 0) return;

    const images: ImageData[] = [];

    Object.entries(latestImageUrls).forEach(([cameraId, imageData]) => {
      // Convert base64 to data URL if needed
      const isBase64 = imageData.startsWith('data:image');
      const src = isBase64 ? imageData : `data:image/jpeg;base64,${imageData}`;

      // Create a temporary image to get dimensions
      const img = new Image();
      img.src = src;

      // Use camera configs if available or use default aspect ratio
      const config = cameraConfigs?.cameras?.[cameraId];
      const aspectRatio = config ? config.resolution.width / config.resolution.height : 4/3;

      images.push({
        src,
        cameraId,
        aspectRatio,
      });
    });

    setProcessedImages(images);
  }, [latestImageUrls, cameraConfigs]);

  // Update container dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        setContainerDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    };

    updateDimensions();
    const resizeObserver = new ResizeObserver(updateDimensions);

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      if (containerRef.current) {
        resizeObserver.unobserve(containerRef.current);
      }
    };
  }, []);

  // Calculate optimal grid layout
  const calculateGridLayout = (images: ImageData[], containerWidth: number, containerHeight: number) => {
    if (images.length === 0) return { cols: 1, rows: 1 };

    // Find the grid configuration that maximizes image size
    let bestLayout = { cols: 1, rows: 1, area: 0 };

    // Try different grid configurations
    for (let cols = 1; cols <= images.length; cols++) {
      const rows = Math.ceil(images.length / cols);

      // Calculate the area each image would get
      const cellWidth = containerWidth / cols;
      const cellHeight = containerHeight / rows;

      // Calculate minimum scaling factor across all images
      let minScale = Infinity;
      images.forEach(image => {
        const scaleWidth = cellWidth / (image.aspectRatio * cellHeight);
        const scaleHeight = cellHeight / (image.aspectRatio === 0 ? 1 : cellWidth / image.aspectRatio);
        minScale = Math.min(minScale, Math.min(scaleWidth, scaleHeight));
      });

      // Calculate effective area
      const effectiveArea = minScale * (cellWidth * cellHeight);

      if (effectiveArea > bestLayout.area) {
        bestLayout = { cols, rows, area: effectiveArea };
      }
    }

    return { cols: bestLayout.cols, rows: bestLayout.rows };
  };

  const { cols, rows } = calculateGridLayout(
    processedImages,
    containerDimensions.width || 1200,
    containerDimensions.height || 800
  );

  return (
    <Box
      ref={containerRef}
      sx={{
        width: '100%',
        height: '100%',
        backgroundColor: theme.palette.background.default,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      {processedImages.length === 0 ? (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
          }}
        >
          <Typography variant="h6" color="text.secondary">
            Waiting for camera feeds...
          </Typography>
        </Box>
      ) : (
        <Grid
          container
          spacing={1}
          sx={{
            height: '100%',
            width: '100%',
            padding: 1,
            boxSizing: 'border-box',
          }}
        >
          {processedImages.map((image, index) => (
            <Grid
              item
              key={image.cameraId}
              xs={12 / cols}
              sx={{
                height: `${100 / rows}%`,
                padding: '4px',
                boxSizing: 'border-box',
              }}
            >
              <Paper
                elevation={3}
                sx={{
                  height: '100%',
                  width: '100%',
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                }}
              >
                <Box
                  sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    backgroundColor: 'rgba(0,0,0,0.5)',
                    color: 'white',
                    padding: '2px 8px',
                    borderBottomRightRadius: '4px',
                    fontSize: '0.8rem',
                    zIndex: 1,
                  }}
                >
                  Camera {cameraConfigs[image.cameraId].camera_index} ({image.cameraId})
                </Box>
                <Box
                  sx={{
                    height: '100%',
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden',
                  }}
                >
                  <Box
                    component="img"
                    src={image.src}
                    alt={`Camera ${image.cameraId}`}
                    sx={{
                      maxWidth: '100%',
                      maxHeight: '100%',
                      objectFit: 'contain',
                    }}
                  />
                </Box>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};



const CameraGridDisplay: React.FC = () => {
  const { latestImageUrls } = useLatestImagesContext();
  const [isLoading, setIsLoading] = useState(true);
  const hasImages = latestImageUrls && Object.keys(latestImageUrls).length > 0;

  // Simulate checking connection status
  useEffect(() => {
    const timeout = setTimeout(() => {
      setIsLoading(false);
    }, 3000); // Set loading state to false after 3 seconds

    return () => clearTimeout(timeout);
  }, []);

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {isLoading ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            gap: 2,
          }}
        >
          <CircularProgress />
          <Typography variant="h6" color="text.secondary">
            Connecting to camera feed...
          </Typography>
        </Box>
      ) : !hasImages ? (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
          }}
        >
          <Typography variant="h6" color="text.secondary">
            No camera feeds available
          </Typography>
        </Box>
      ) : (
        <Box
          sx={{
            flexGrow: 1,
            width: '100%',
            overflow: 'hidden',
          }}
        >
          <ImageGrid />
        </Box>
      )}
    </Box>
  );
};

export default CameraGridDisplay;
