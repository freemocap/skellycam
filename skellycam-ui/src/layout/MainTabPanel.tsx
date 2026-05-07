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
        <div className="flex flex-col h-full">
            <div className="main-tab-bar">
                <SegmentedControl
                    options={[
                        { label: t('cameras'), value: 'cameras' },
                        { label: t('videoPlayback'), value: 'playback' },
                    ]}
                    value={activeTab}
                    onChange={(v) => navigate('/' + v)}
                    size="md"
                />
            </div>
            <div className="flex-1 overflow-hidden">
                <BaseContentRouter />
            </div>
        </div>
    );
};
