// skellycam-ui/src/layout/BaseContent.tsx
import React from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Footer} from "@/components/ui-components/Footer";
import {useTheme} from "@mui/material/styles";
import {CameraViewsGrid} from "@/components/camera-views/CameraViewsGrid";

export const CamerasPage = () => {
    const theme = useTheme();

    return (
        <React.Fragment>
            <Box sx={{
                py: 1,
                px: 1,
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                width: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                overflow: "scroll"

            }}>
                {/*<CamerasViewSettingsOverlay/>*/}

                <Box>
                    <ErrorBoundary>
                        <CameraViewsGrid/>
                    </ErrorBoundary>
                </Box>
                <Box component="footer" sx={{p: 1}}>
                    <Footer/>
                </Box>
            </Box>
        </React.Fragment>
    )
}
