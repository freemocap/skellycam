import React, { useRef, useState } from "react";
import ReactDOM from "react-dom";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { CameraGridSettingsModal } from "@/components/camera-views/CameraGridSettingsModal";
import { ROTATION_DEGREE_LABELS, RotationValue, useAppDispatch } from "@/store";
import { cameraSelectionToggled } from "@/store/slices/cameras/cameras-slice";
import { Camera } from "@/store/slices/cameras/cameras-types";

interface CameraTreeItemProps {
    camera: Camera;
}

const getConfigSummary = (config: any): string[] => {
    const summary: string[] = [];
    if (!config) return summary;
    if (config.resolution?.width && config.resolution?.height) {
        summary.push(`${config.resolution.width}×${config.resolution.height}`);
    }
    if (config.exposure !== undefined && config.exposure_mode === 'MANUAL') {
        summary.push(`E:${config.exposure}`);
    }
    if (config.rotation) summary.push(ROTATION_DEGREE_LABELS[config.rotation as RotationValue]);
    if (config.capture_fourcc) summary.push(config.capture_fourcc);
    return summary.filter(Boolean);
};

export const CameraTreeItem: React.FC<CameraTreeItemProps> = ({ camera }) => {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [modalPos, setModalPos] = useState<{ top: number; right: number }>({ top: 80, right: 40 });
    const settingsBtnRef = useRef<HTMLButtonElement>(null);

    const handleToggleSelection = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(cameraSelectionToggled(camera.id));
    };

    const handleOpenSettings = (e: React.MouseEvent): void => {
        e.stopPropagation();
        if (!settingsOpen && settingsBtnRef.current) {
            const rect = settingsBtnRef.current.getBoundingClientRect();
            setModalPos({ top: rect.bottom + 8, right: window.innerWidth - rect.right });
        }
        setSettingsOpen(prev => !prev);
    };

    const configSummary = getConfigSummary(camera.desiredConfig);

    return (
        <div className="camera-item-row br-1 flex flex-col gap-1 p-1" style={{ borderBottom: '1px solid var(--gray-800)' }}>
            {/* Row 1 — selection, name, settings */}
            <div className="flex items-center gap-1">
                <button className="button icon-button" onClick={handleToggleSelection}>
                    <span className={clsx("icon icon-size-16", camera.selected ? "connected-icon" : "warning-icon")} />
                </button>

                <p className="text sm text-white text-nowrap" style={{ minWidth: 72 }}>Camera {camera.index}</p>
                <p className="text sm text-gray text-nowrap" style={{ flex: '0 1 auto', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {camera.name}
                </p>

                <div className="flex-1" />

                <button
                    ref={settingsBtnRef}
                    className={clsx("button icon-button", settingsOpen && "activated")}
                    onClick={handleOpenSettings}
                    title={t('cameraSettings')}
                >
                    <span className={clsx("icon icon-size-16", settingsOpen ? "close-icon" : "settings-icon")} />
                </button>
            </div>

            {/* Row 2 — config chips */}
            {configSummary.length > 0 && (
                <div className="flex flex-wrap gap-1">
                    {configSummary.map(item => (
                        <span key={item} className="camera-config-chip">{item}</span>
                    ))}
                </div>
            )}

            {settingsOpen && ReactDOM.createPortal(
                <CameraGridSettingsModal
                    camera={camera}
                    initialPos={modalPos}
                    onClose={() => setSettingsOpen(false)}
                />,
                document.body
            )}
        </div>
    );
};
