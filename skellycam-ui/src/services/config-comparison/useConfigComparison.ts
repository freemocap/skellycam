import {selectConnectedCameraConfig} from "@/store/slices/cameras-slices/connectedCameraConfigsSlice";
import {selectHasPendingChanges, selectUserCameraConfig} from "@/store/slices/cameras-slices/userCameraConfigs";
import {CameraConfig} from "@/store/slices/cameras-slices/camera-types";
import {useAppSelector} from "@/store/AppStateStore";

interface ConfigComparison {
    hasDifferences: boolean;
    hasPendingChanges: boolean;
    differences: Partial<Record<keyof CameraConfig, {
        current: any;
        pending: any;
    }>>;
}

export const useConfigComparison = (deviceId: string): ConfigComparison => {
    const connectedConfig = useAppSelector(selectConnectedCameraConfig(deviceId));
    const userConfig = useAppSelector(selectUserCameraConfig(deviceId));
    const hasPendingChanges = useAppSelector(selectHasPendingChanges(deviceId));

    // Compare configurations and return differences
    const differences: ConfigComparison['differences'] = {};

    if (connectedConfig && userConfig) {
        Object.keys(userConfig).forEach((key) => {
            const k = key as keyof CameraConfig;
            if (JSON.stringify(connectedConfig[k]) !== JSON.stringify(userConfig[k])) {
                differences[k] = {
                    current: connectedConfig[k],
                    pending: userConfig[k],
                };
            }
        });
    }

    return {
        hasDifferences: Object.keys(differences).length > 0,
        hasPendingChanges,
        differences,
    };
};
