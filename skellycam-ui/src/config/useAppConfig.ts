import {useCallback, useEffect, useState} from "react";
import {urlService} from "@/config/appUrlService";

export interface AppConfig {
    startServer: boolean;
    serverExecutablePath: string;
    limitFramerate: boolean;
    framerate: number;
    preShrink: boolean;
    shrinkFactor: number;
}

 const DEFAULT_CONFIG: AppConfig = {

    startServer: true,
    serverExecutablePath: '',
    limitFramerate: false,
    framerate: 30,
    preShrink: true,
    shrinkFactor: .5
};
export let currentConfig: AppConfig = { ...DEFAULT_CONFIG };
export const useAppConfig = () => {
    const [appConfig, setAppConfigState] = useState<AppConfig | null>(null);

    // Load config on mount
    useEffect(() => {
        const loadConfig = async () => {
            try {
                const savedConfig = await window.electronAPI.getAppConfig();
                setAppConfigState(prev => ({...prev, ...savedConfig}));
            } catch (error) {
                console.warn('Failed to load config, using defaults', error);
            }
        };

        loadConfig();

        // Listen for config updates from main process
        const handleConfigUpdate = (_: any, updatedConfig: AppConfig) => {
            setAppConfigState(updatedConfig);
        };

        window.electronAPI.onAppConfigUpdate(handleConfigUpdate);

        return () => {
            window.electronAPI.removeAppConfigUpdateListener(handleConfigUpdate);
        };
    }, []);

    const setConfig = useCallback(async (newConfig: Partial<AppConfig>) => {
        const updatedConfig = {...appConfig, ...newConfig} as AppConfig;
        setAppConfigState(updatedConfig);
        try {
            await window.electronAPI.setAppConfig(updatedConfig);
        } catch (error) {
            console.error('Failed to save config:', error);
        }
    }, [appConfig]);


    return {
        appConfig,
        setConfig,
    };
}
