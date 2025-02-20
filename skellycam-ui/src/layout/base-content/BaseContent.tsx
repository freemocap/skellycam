import React from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Router} from "@/layout/routing/router";
import {Copyright} from "@/components/ui-components/Copyright";
import extendedPaperbaseTheme from "@/layout/base-content/paperbase_theme/paperbase-theme";

export const BaseContent = () => {
    return (
        <React.Fragment>
            <Box sx={{
                py: 6,
                px: 4,
                flex: 1,
                height: '100%',
                bgcolor: extendedPaperbaseTheme.palette.primary.main,
                borderStyle: 'solid', borderWidth: '1px', borderColor: extendedPaperbaseTheme.palette.divider
            }}>
                <ErrorBoundary>
                    <Router/>
                </ErrorBoundary>
                <Box component="footer" sx={{p: 1}}>
                    <Copyright />
                </Box>
            </Box>
        </React.Fragment>
    )
}
