import * as React from "react";
import { useTranslation } from "react-i18next";
import { EXTERNAL_URLS } from "@/constants/external-urls";

export const Footer = function () {
    const { t } = useTranslation();

    return (
        <p className="footer-content text sm text-gray text-center">
            {t('footerWith') + ' '}
            <a
                className="text-gray"
                href={EXTERNAL_URLS.GITHUB_ORG}
                target="_blank"
                rel="noopener noreferrer"
            >
                ❤️
            </a>
            {' ' + t('footerFrom') + ' '}
            <a
                className="text-gray"
                href={EXTERNAL_URLS.GITHUB_ORG}
                target="_blank"
                rel="noopener noreferrer"
            >
                {t('footerOrgName')}
            </a>
            {' '}{new Date().getFullYear()}
        </p>
            //  <ButtonSm
            //                     iconClass=""
            //                     text={t('roadmap')}
            //                     rightSideIcon="externallink"
            //                     textColor="text-gray"
            //                     onClick={() => window.open(EXTERNAL_URLS.ROADMAP, '_blank')}
            //                 />
    );
};
