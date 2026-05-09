import React, { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { useTranslation } from 'react-i18next';
import { useAppVersion } from '@/hooks/useAppVersion';
import { useAutoUpdate } from '@/hooks/useAutoUpdate';
import { EXTERNAL_URLS } from '@/constants/external-urls';

interface VersionChipProps {
    variant?: 'compact' | 'full';
}

type ToastType = 'success' | 'error' | 'info';

export const VersionChip: React.FC<VersionChipProps> = ({ variant = 'full' }) => {
    const { t } = useTranslation();
    const version = useAppVersion();
    const { status, version: updateVersion, errorMessage, checkForUpdate } = useAutoUpdate();

    const isChecking = status === 'checking';
    const prevStatusRef = useRef(status);

    const [showSuccess, setShowSuccess] = useState(false);
    const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);

    useEffect(() => {
        const prev = prevStatusRef.current;
        prevStatusRef.current = status;
        if (prev !== 'checking') return;

        if (status === 'up-to-date') {
            setToast({ message: t('upToDate'), type: 'success' });
            setShowSuccess(true);
            setTimeout(() => setShowSuccess(false), 3000);
        } else if (status === 'available') {
            setToast({ message: t('updateAvailableMessage', { version: updateVersion }), type: 'info' });
        } else if (status === 'error') {
            setToast({
                message: errorMessage ? `${t('updateError')}: ${errorMessage}` : t('updateError'),
                type: 'error',
            });
        }
    }, [status, updateVersion, errorMessage, t]);

    useEffect(() => {
        if (!toast) return;
        const timer = setTimeout(() => setToast(null), 4000);
        return () => clearTimeout(timer);
    }, [toast]);

    if (!version) return null;

    return (
        <div className="version-button-container pos-abs flex flex-row items-center gap-2">
            <button
                className={clsx("version-badge", showSuccess && "success")}
                onClick={checkForUpdate}
                disabled={isChecking}
                title={t('checkForUpdates')}
            >
    <span
        className={clsx(
            "icon icon-size-16",
            isChecking
                ? "updateAvailable-icon"
                : showSuccess
                ? "upToDate-icon"
                : "checkUpdate-icon"
        )}
    />
    v{version}
</button>

            <button
                className="button icon icon-size-16 github-icon"
                onClick={() => window.open(EXTERNAL_URLS.GITHUB_RELEASES, '_blank')}
                title="GitHub Releases"
            >
                <span className="icon icon-size-16 externallink-icon" />
                
            </button>

            {toast && (
                <div className={clsx("toast-notification", toast.type)}>
                    <p className="text sm">{toast.message}</p>
                </div>
            )}
        </div>
    );
};
