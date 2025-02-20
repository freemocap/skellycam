import * as React from 'react';
import {ThemeProvider} from '@mui/material/styles';
import {HashRouter} from 'react-router-dom';
import {CssBaseline} from "@mui/material";
import {BaseContent} from "@/layout/BaseContent";
import {BasePanelLayout} from "@/layout/BasePanelLayout";
import extendedPaperbaseTheme from "@/layout/paperbase_theme/paperbase-theme";

export const PaperbaseContent = function () {

    return (
        <ThemeProvider theme={extendedPaperbaseTheme}>
            <CssBaseline/>
            <HashRouter>
                <BasePanelLayout>
                    <BaseContent/>
                </BasePanelLayout>
            </HashRouter>
        </ThemeProvider>
    );
}
