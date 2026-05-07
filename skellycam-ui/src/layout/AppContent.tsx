import * as React from 'react';
import {HashRouter} from 'react-router-dom';
import {BasePanelLayout} from "@/layout/BasePanelLayout";
import {BaseContentRouter} from "@/layout/BaseContentRouter";
import {UpdateBanner} from "@/components/ui-components/UpdateBanner";
import {AutoUpdateProvider} from "@/hooks/AutoUpdateContext";
import {useTranslation} from "react-i18next";
import {getLocaleDirection} from "@/i18n";

export const AppContent = function () {
    const {i18n} = useTranslation();
    const direction = getLocaleDirection(i18n.language);

    React.useEffect(() => {
        document.documentElement.dir = direction;
        document.documentElement.lang = i18n.language;
    }, [direction, i18n.language]);

    return (
        <HashRouter>
            <AutoUpdateProvider>
                <BasePanelLayout>
                    <BaseContentRouter/>
                </BasePanelLayout>
                <UpdateBanner/>
            </AutoUpdateProvider>
        </HashRouter>
    );
}
