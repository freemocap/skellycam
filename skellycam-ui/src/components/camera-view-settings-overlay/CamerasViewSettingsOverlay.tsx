import React, { useRef, useState } from 'react';
import clsx from 'clsx';
import ToggleComponent from '@/components/ui-components/ToggleComponent';
import SubactionHeader from '@/components/ui-components/SubactionHeader';
import ValueSelector from '@/components/ui-components/ValueSelector';
import ButtonSm from '@/components/ui-components/ButtonSm';
import { useServer } from '@/services/server/ServerContextProvider';
import { useTranslation } from 'react-i18next';

interface CameraSettings { columns: number | null; }

interface CamerasViewSettingsOverlayProps {
    onSettingsChange: (settings: CameraSettings) => void;
    onResetLayout: () => void;
    /** When true, renders the trigger inline (no absolute positioning).
     *  The panel drops down using position:fixed anchored to the button. */
    inline?: boolean;
}

export const CamerasViewSettingsOverlay: React.FC<CamerasViewSettingsOverlayProps> = ({
    onSettingsChange,
    inline = false,
}) => {
    const { connectedCameraIds } = useServer();
    const { t } = useTranslation();
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const [isAuto, setIsAuto] = useState<boolean>(true);
    const [manualColumns, setManualColumns] = useState<number>(2);
    const [panelStyle, setPanelStyle] = useState<React.CSSProperties>({});
    const buttonRef = useRef<HTMLButtonElement>(null);

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

    const handleColumnsChange = (value: number) => {
        setManualColumns(value);
        if (isAuto) setIsAuto(false);
        onSettingsChange({ columns: value });
    };

    const handleToggle = () => {
        if (!isOpen && inline && buttonRef.current) {
            const rect = buttonRef.current.getBoundingClientRect();
            setPanelStyle({
                position: 'fixed',
                top: rect.bottom + 4,
                right: window.innerWidth - rect.right,
                zIndex: 200,
            });
        }
        setIsOpen((prev) => !prev);
    };

    const panel = (
        <div
            className="settings-overlay-panel reveal slide-down bg-dark br-2 border-1 border-black elevated-sharp flex flex-col p-2 gap-1"
            style={inline ? panelStyle : undefined}
        >
            <SubactionHeader text={t("gridColumns")} />

            <ToggleComponent
                text={t("auto")}
                isToggled={isAuto}
                onToggle={handleAutoToggle}
            />

            <div className="toggle-button gap-1 p-1 br-1 flex justify-content-space-between items-center h-25">
                <p className="text md text-gray text-nowrap">{t("columns")}</p>
                <ValueSelector
                    value={isAuto ? autoColumns : manualColumns}
                    min={1}
                    max={8}
                    unit="col"
                    onChange={handleColumnsChange}
                />
            </div>
        </div>
    );

    if (inline) {
        return (
            <>
                <button
                    ref={buttonRef}
                    className="button icon-button br-1 border-1 border-black bg-dark"
                    onClick={handleToggle}
                    title={isOpen ? t("closeSettings") : t("gridSettings")}
                >
                    <span className={clsx("icon icon-size-16", isOpen ? "close-icon" : "settings-icon")} />
                </button>
                {isOpen && panel}
            </>
        );
    }

    return (
      <>
        <div className="mode-header live-mode w-full reveal fadeIn active-tools-header br-1-1 gap-1 p-1 flex justify-content-space-between">
          <div className="all-actions-components flex flex-row">
            <div className="stream-actions-container flex flex-row gap-1">
              <ButtonSm
                text="Stream"
                iconClass="stream-icon"
                textColor="text-white"
                onClick={() => {}}
              />
              <button className="button icon-button" onClick="">
                <span className="icon icon-size-16 pause-icon" />
              </button>
            </div>
            <div className='configure-camera-action-container flex flex-row gap-1'>
                   <button className="button icon-button"
                        onClick="">
                        <span className="icon icon-size-16 scan-icon" />
                    </button>
                <ButtonSm
                                text="Configure"
                                className="dropdown"
                                rightSideIcon = "dropdown"
                                iconClass="settings-icon"
                                textColor="text-white"
                                onClick={() => {}} //add logic to open camera configuration modal
                            />

            </div>
          </div>
          <div className="settings-overlay-trigger"></div>
          <button
            className="button icon-button br-1 border-1 border-black bg-dark"
            onClick={handleToggle}
            title={isOpen ? t("closeSettings") : t("gridSettings")}
          >
            <span
              className={clsx(
                "icon icon-size-16",
                isOpen ? "close-icon" : "settings-icon",
              )}
            />
          </button>
        </div>
        {isOpen && panel}
      </>
    );
};
