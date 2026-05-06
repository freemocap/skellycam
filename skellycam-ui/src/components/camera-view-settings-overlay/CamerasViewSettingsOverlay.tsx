import React, { useState } from 'react';
import clsx from 'clsx';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';

interface CameraSettings { columns: number | null; }

interface CamerasViewSettingsOverlayProps {
    onSettingsChange: (settings: CameraSettings) => void;
    onResetLayout: () => void;
}

export const CamerasViewSettingsOverlay: React.FC<CamerasViewSettingsOverlayProps> = ({
    onSettingsChange,
}) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(true);
    const [manualColumns, setManualColumns] = useState<number>(2);

    const getAutoColumns = (total: number): number => {
        if (total <= 1) return 1;
        if (total <= 4) return 2;
        if (total <= 9) return 3;
        return 4;
    };
    const autoColumns = getAutoColumns(connectedCameraIds.length);

    const handleAutoToggle = (checked: boolean) => {
        setIsAuto(checked);
        onSettingsChange({ columns: checked ? null : manualColumns });
    };

    const handleColumnsChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = parseInt(e.target.value);
        if (!isNaN(value) && value > 0) {
            setManualColumns(value);
            if (isAuto) setIsAuto(false);
            onSettingsChange({ columns: value });
        }
    };

    return (
        <>
            <div className="settings-overlay-trigger">
                <button
                    className="button icon-button br-1 border-1 border-black bg-dark"
                    onClick={() => setIsOpen(!isOpen)}
                    title={isOpen ? t("closeSettings") : t("gridSettings")}
                >
                    <span className={clsx("icon icon-size-16", isOpen ? "close-icon" : "settings-icon")} />
                </button>
            </div>

            {isOpen && (
                <div className="settings-overlay-panel reveal slide-down bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-2 gap-1">
                    <SubactionHeader text={t("gridColumns")} />

                    <ToggleComponent
                        text={t("auto")}
                        isToggled={isAuto}
                        onToggle={handleAutoToggle}
                    />

                    <div className="toggle-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                        <p className="text md text-gray text-nowrap">{t("columns")}</p>
                        <div className="input-with-unit">
                            <input
                                className="input-field numeric-input"
                                type="number"
                                min={1}
                                value={isAuto ? autoColumns : manualColumns}
                                onChange={handleColumnsChange}
                            />
                        </div>
                    </div>

                    {isAuto && (
                        <p className="text sm text-darkgray p-1">Auto: {autoColumns}</p>
                    )}
                </div>
            )}
        </>
    );
};
