import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useElectronIPC } from '@/services';
import { useAppDispatch } from '@/store';
import { camerasConnectOrUpdate } from '@/store/slices/cameras/cameras-thunks';
import { EXTERNAL_URLS } from '@/constants/external-urls';
import { LanguageSwitcher } from '@/components/languages/LanguageSwitcher';
import { VersionChip } from '@/components/ui-components/VersionChip';
import DesignerCheckbox from '@/components/ui-components/Checkbox';
import ButtonSm from '@/components/ui-components/ButtonSm';
import ButtonCard from '@/components/ui-components/ButtonCard';

export const HomePage: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
    const [telemetryEnabled, setTelemetryEnabled] = useState<boolean>(true);
    const [telemetryLoaded, setTelemetryLoaded] = useState<boolean>(false);
    const { isElectron, api } = useElectronIPC();

    useEffect(() => {
        const fetchLogo = async (): Promise<void> => {
            try {
                if (isElectron && api) {
                    const dataUrl = await api.assets.getLogoBase64.query();
                    if (dataUrl) setLogoDataUrl(dataUrl);
                }
            } catch (error) {
                console.error('Failed to load logo:', error);
            }
        };
        fetchLogo();
    }, [isElectron, api]);

    useEffect(() => {
        const loadTelemetryPref = async (): Promise<void> => {
            try {
                if (isElectron && api) {
                    const enabled = await api.telemetry.getEnabled.query();
                    setTelemetryEnabled(enabled);
                }
            } catch (error) {
                console.error('Failed to load telemetry preference:', error);
            } finally {
                setTelemetryLoaded(true);
            }
        };
        loadTelemetryPref();
    }, [isElectron, api]);

    const handleTelemetryToggle = useCallback(async (checked: boolean) => {
        setTelemetryEnabled(checked);
        try {
            if (isElectron && api) {
                await api.telemetry.setEnabled.mutate({ enabled: checked });
            }
        } catch (error) {
            console.error('Failed to save telemetry preference:', error);
        }
    }, [isElectron, api]);

    const handleGoToCameras = useCallback(() => {
        navigate('/cameras');
        dispatch(camerasConnectOrUpdate());
    }, [navigate, dispatch]);

    const handleGoToPlayback = useCallback(() => {
        navigate('/playback');
    }, [navigate]);

    return (
        <div className="home-page overflow-hidden flex-1 bg-middark br-1 flex flex-row gap-3 p-2">
            {/* Left column — logo */}
            <div className="splash-image-container flex flex-1">
            </div>

            {/* Right column — content */}
            <div className="flex-1 flex flex-col gap-3 p-1 justify-center">
                <h1 className="title">
                    <span className="text-white">{t('welcomeTitle')}</span>
                    <br />
                    <span className="text-gray">{t('welcomeSubtitle')}</span>
                </h1>

                <div className="flex gap-2">
                    <ButtonCard
                        text={t('connectToCameras')}
                        iconClass="live-icon icon-size-42"
                        onClick={handleGoToCameras}
                    />
                    <ButtonCard
                        text={t('videoPlayback')}
                        iconClass="importVideos-icon icon-size-42"
                        onClick={handleGoToPlayback}
                    />
                </div>

                {telemetryLoaded && (
                    <DesignerCheckbox
                        label={t('sendAnonymousPings')}
                        checked={telemetryEnabled}
                        onChange={(e) => handleTelemetryToggle(e.target.checked)}
                    />
                )}

                <ButtonSm
                    iconClass="learn-icon"
                    text={t('documentation')}
                    rightSideIcon="externallink"
                    textColor="text-gray"
                    onClick={() => window.open(EXTERNAL_URLS.DOCS_INTRO, '_blank')}
                />
                <ButtonSm
                    iconClass="discord-icon"
                    text="Join community"
                    rightSideIcon="externallink"
                    textColor="text-gray"
                    onClick={() => window.open(EXTERNAL_URLS.DISCORD, '_blank')}
                />
            </div>
        </div>
    );
};
