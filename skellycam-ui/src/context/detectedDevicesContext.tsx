import React, {createContext, useContext, useEffect, useState} from 'react';
import {useDetectDevices} from "@/hooks/useDetectDevices";

type CameraContextType = {
    detectedDevices: MediaDeviceInfo[];
    refreshDetectedDevices: () => Promise<void>;
};

const CameraContext = createContext<CameraContextType>({
    detectedDevices: [],
    refreshDetectedDevices: async () => {
    }
});

export const CameraProvider = ({children}: { children: React.ReactNode }) => {
    const [detectedDevices, setDetectedDevices] = useState<MediaDeviceInfo[]>([]);

    const refreshDetectedDevices = async () => {
        const cam = new useDetectDevices();
        const deviceInfos = await cam.findAllCameras(false);
        setDetectedDevices(deviceInfos);
    };

    useEffect(() => {
        refreshDetectedDevices().then(
            () => console.log('Detected devices refreshed successfully.')
        ).catch(
            (error) => console.error('Error refreshing detected devices:', error)
        )
    }, []);

    return (
        <CameraContext.Provider value={{detectedDevices, refreshDetectedDevices}}>
            {children}
        </CameraContext.Provider>
    );
};

export const useDetectedDevicesContext = () => useContext(CameraContext);
