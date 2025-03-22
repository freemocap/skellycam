import React, {useEffect} from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Copyright} from "@/components/ui-components/Copyright";
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";
import {CamerasView} from "@/components/camera-views/CamerasView";
import {useAppDispatch} from "@/store/hooks";
import {detectBrowserDevices} from "@/store/thunks/camera-thunks";

export const BaseContent = () => {
    const dispatch = useAppDispatch();

    return (
        <React.Fragment>
            <Box sx={{
                py: 6,
                px: 4,
                flex: 1,
                height: '100%',
                backgroundColor: extendedPaperbaseTheme.palette.primary.main,
                borderStyle: 'solid', borderWidth: '1px', borderColor: extendedPaperbaseTheme.palette.divider
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
