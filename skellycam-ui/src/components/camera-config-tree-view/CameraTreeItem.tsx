import React, { useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import { CameraConfigTreeSection } from "./CameraConfigTreeSection";
import { ROTATION_DEGREE_LABELS, RotationValue, useAppDispatch } from "@/store";
import { cameraSelectionToggled } from "@/store/slices/cameras/cameras-slice";
import { Camera } from "@/store/slices/cameras/cameras-types";

interface CameraTreeItemProps {
    camera: Camera;
    isExpanded?: boolean;
}

const getConfigSummary = (config: any): string[] => {
    const summary: string[] = [];
    if (!config) return summary;
    if (config.resolution?.width && config.resolution?.height) {
        summary.push(`${config.resolution.width}×${config.resolution.height}`);
    }
    if (config.framerate) summary.push(`${parseFloat(config.framerate).toFixed(0)}fps`);
    if (config.exposure !== undefined && config.exposure_mode === 'MANUAL') {
        summary.push(`E:${config.exposure}`);
    }
    if (config.pixel_format && config.pixel_format !== 'RGB') summary.push(config.pixel_format);
    if (config.rotation) summary.push(ROTATION_DEGREE_LABELS[config.rotation as RotationValue]);
    if (config.capture_fourcc) summary.push(config.capture_fourcc);
    return summary.filter(Boolean);
};

export const CameraTreeItem: React.FC<CameraTreeItemProps> = ({ camera }) => {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const [localExpanded, setLocalExpanded] = useState(false);

    const statusLabelMap: Record<string, string> = {
        connected: t('connected'),
        available: t('available'),
        error: t('errorsDetected'),
    };

    const handleToggleSelection = (e: React.MouseEvent): void => {
        e.stopPropagation();
        dispatch(cameraSelectionToggled(camera.id));
    };

    const configSummary = getConfigSummary(camera.desiredConfig);
    const showConfigSummary = !localExpanded && configSummary.length > 0;

    return (
        <div className="flex flex-col">
            <div
                className={clsx("camera-item-row toggle-button gap-1 p-1 br-1 flex items-center h-25", localExpanded && "expanded")}
                onClick={() => setLocalExpanded(prev => !prev)}
            >
                {/* Selection toggle */}
                <button
                    className="button icon-button"
                    onClick={handleToggleSelection}
                >
                    <span className={clsx("icon icon-size-16", camera.selected ? "connected-icon" : "warning-icon")} />
                </button>

                {/* Camera icon + status color */}
                <span className={clsx("icon stream-icon icon-size-16", `camera-status-${camera.connectionStatus}`)} />

                {/* Name */}
                <div className="flex flex-col flex-1 overflow-hidden">
                    <p className="text sm text-nowrap">Camera #{camera.index}</p>
                    <p className="text sm text-gray text-nowrap" style={{ fontSize: '0.6rem' }}>{camera.name}</p>
                </div>

                {/* Config summary chips */}
                {showConfigSummary && configSummary.slice(0, 5).map((item) => (
                    <span key={item} className="camera-config-chip">{item}</span>
                ))}

                {/* Status badge */}
                <span className={clsx("camera-status-badge", `camera-status-${camera.connectionStatus}`)}>
                    {statusLabelMap[camera.connectionStatus] ?? camera.connectionStatus.toUpperCase()}
                </span>
            </div>

            {localExpanded && <CameraConfigTreeSection camera={camera} />}
        </div>
    );
};
