import * as React from 'react';
import {useTranslation} from "react-i18next";

export const PlaybackSidebarPanel: React.FC = () => {
    const {t} = useTranslation();

    return (
        <div className="flex flex-col gap-1 h-full p-1">
            <div className="flex flex-col gap-1 p-2 bg-surface br-2 border-mid-black border-1">
                <span className="text-sm text-muted">{t('playbackSidebar', 'Playback sidebar')}</span>
                <span className="text-xs text-muted">{t('playbackSidebarComingSoon', 'Coming soon')}</span>
            </div>
        </div>
    );
};
