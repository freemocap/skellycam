import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import SegmentedControl from '@/components/ui-components/SegmentedControl';
import { BaseContentRouter } from '@/layout/BaseContentRouter';

export const MainTabPanel: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { t } = useTranslation();

    const activeTab = location.pathname.startsWith('/playback') ? 'playback' : 'cameras';

    return (
        <div className="main-container gap-1 overflow-hidden flex flex-row flex-1 pos-rel">
            {/* <div className="segmented-control-container br-1-1 gap-1 p-1 bg-middark flex main-segmented-control"> */}
                <SegmentedControl
                    options={[
                        { label: t('cameras'), value: 'cameras' },
                        { label: t('videoPlayback'), value: 'playback' },
                    ]}
                    value={activeTab}
                    onChange={(v) => navigate('/' + v)}
                    size="md"
                />
            {/* </div> */}
            <div className="mode-container flex-5 br-2 bg-darkgray border-mid-black border-1 overflow-hidden flex flex-col flex-1 gap-1 p-1">
                <BaseContentRouter />
            </div>
        </div>
    );
};
