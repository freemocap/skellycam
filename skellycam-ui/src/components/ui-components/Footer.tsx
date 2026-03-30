import Typography from "@mui/material/Typography";
import Link from "@mui/material/Link";
import * as React from "react";
import {useTheme} from "@mui/material";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import {useTranslation} from "react-i18next";
import {EXTERNAL_URLS} from "@/constants/external-urls";

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
            <Link color="inherit" href={EXTERNAL_URLS.GITHUB_ORG} target="_blank" rel="noopener noreferrer"
                  sx={{display: 'inline-flex', alignItems: 'center'}}>
                ❤️
            </Link>{'  ' + t('footerFrom') + ' '}
            <Link color="inherit" href={EXTERNAL_URLS.GITHUB_ORG} target="_blank" rel="noopener noreferrer"
                  sx={{display: 'inline-flex', alignItems: 'center', gap: 0.3}}>
                {t('footerOrgName')}
                <OpenInNewIcon sx={{fontSize: 12}} />
            </Link>{' '}
            {new Date().getFullYear()}
        </Typography>
    );
}
