import React from "react";
import { TreeItem } from "@mui/x-tree-view/TreeItem";
import { useAppDispatch } from "@/store";
import { cameraConfigUpdated } from "@/store/slices/cameras/cameras-slice";
import { CameraDevice, CameraConfig } from "@/store/slices/cameras/cameras-types";
import {CameraConfigPanel} from "@/components/available-cameras-panel/CameraConfigPanel";

interface CameraConfigTreeSectionProps {
    camera: CameraDevice;
}

export const CameraConfigTreeSection: React.FC<CameraConfigTreeSectionProps> = ({
                                                                                    camera,
                                                                                }) => {
    const dispatch = useAppDispatch();

    const handleConfigChange = (newConfig: CameraConfig): void => {
        dispatch(
            cameraConfigUpdated({
                cameraId: camera.cameraId,
                config: newConfig,
            })
        );
    };

    return (
        <TreeItem
            itemId={`camera-${camera.cameraId}-config`}
            label={
                <CameraConfigPanel
                    config={camera.config}
                    onConfigChange={handleConfigChange}
                    isExpanded={true}
                />
            }
        />
    );
};
