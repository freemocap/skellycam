// skellycam-ui/src/layout/BaseContent.tsx
import React from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Copyright} from "@/components/ui-components/Copyright";
import {CamerasView} from "@/components/camera-views/CamerasView";
import {useTheme} from "@mui/material/styles";

export const BaseContent = () => {
    const theme = useTheme();

    return (
        <React.Fragment>
            <Box sx={{
                py: 6,
                px: 4,
                flex: 1,
                height: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: theme.palette.divider
            }}>
                <ErrorBoundary>
                    <CamerasView/>
                </ErrorBoundary>
                <Box component="footer" sx={{p: 1}}>
                    <Copyright />
                </Box>
            </Box>
        </React.Fragment>
    )
}
