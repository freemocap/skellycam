import * as React from 'react';
import {ThemeProvider} from '@mui/material/styles';
import {HashRouter} from 'react-router-dom';
import {CssBaseline} from "@mui/material";
import {BasePanelLayout} from "@/layout/BasePanelLayout";
import {createExtendedTheme} from "@/layout/paperbase_theme/paperbase-theme";
import {useAppSelector} from "@/store";
import {selectThemeMode} from "@/store/slices/theme/theme-selectors";
import {BaseContentRouter} from "@/layout/BaseContentRouter";

export const PaperbaseContent = function () {

    const themeMode = useAppSelector(selectThemeMode);
    // Create theme dynamically based on current mode

    const theme = React.useMemo(() =>
            createExtendedTheme(themeMode),
        [themeMode]
    );
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline/>
            <HashRouter>
                <BasePanelLayout>
                    <BaseContentRouter/>
                </BasePanelLayout>
            </HashRouter>
        </ThemeProvider>
    );
}
