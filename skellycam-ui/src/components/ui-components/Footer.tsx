import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import * as React from "react";
import {useTheme} from "@mui/material";
import {useTranslation} from "react-i18next";

export const Footer = function () {
    const theme = useTheme();
    const {t} = useTranslation();

    return (
        <Typography
            variant="body2"
            color={theme.palette.mode === 'dark' ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.6)"}
            align="center"
        >
            {t('footerWith') + ' '}
            <Link color="inherit" href="https://github.com/freemocap/">
                ❤️
            </Link>{'  ' + t('footerFrom') + ' '}
            <Link color="inherit" href="https://github.com/freemocap/">
                {t('footerOrgName')}
            </Link>{' '}
            {new Date().getFullYear()}
        </Typography>
    );
}
