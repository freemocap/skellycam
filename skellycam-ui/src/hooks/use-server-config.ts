// hooks/useServerConfig.ts
import { useState, useEffect } from 'react';

export interface ServerConfig {
    host: string;
    port: number;
    autoConnect: boolean;
}

const STORAGE_KEY = 'skellycam-server-config';

const defaultConfig: ServerConfig = {
    host: 'localhost',
    port: 8006,
    autoConnect: true,
};

export const useServerConfig = () => {
    const [config, setConfig] = useState<ServerConfig>(() => {
        // Load from localStorage on init
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                return { ...defaultConfig, ...JSON.parse(stored) };
            }
        } catch (error) {
            console.error('Failed to load server config:', error);
        }
        return defaultConfig;
    });

    // Save to localStorage whenever config changes
    useEffect(() => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
        } catch (error) {
            console.error('Failed to save server config:', error);
        }
    }, [config]);

    const updateConfig = (updates: Partial<ServerConfig>) => {
        setConfig(prev => ({ ...prev, ...updates }));
    };

    const getBaseHttpUrl = () => {
        return `http://${config.host}:${config.port}`;
    };

    const getApiUrl = (path: string) => {
        return `${getBaseHttpUrl()}${path}`;
    };

    const getWebSocketUrl = () => {
        return `ws://${config.host}:${config.port}/skellycam/websocket/connect`;
    };

    const getHttpEndpointUrls = () => {
        return {
            health: getApiUrl('/health'),
            shutdown: getApiUrl('/shutdown'),
            detectCameras: getApiUrl('/skellycam/camera/detect'),
            createGroup: getApiUrl('/skellycam/camera/group/apply'),
            closeAll: getApiUrl('/skellycam/camera/group/close/all'),
            updateConfigs: getApiUrl('/skellycam/camera/update'),
            startRecording: getApiUrl('/skellycam/camera/group/all/record/start'),
            stopRecording: getApiUrl('/skellycam/camera/group/all/record/stop'),
            pauseUnpauseCameras: getApiUrl('/skellycam/camera/group/all/pause_unpause'),
        };
    };

    return {
        config,
        updateConfig,
        getBaseHttpUrl,
        getApiUrl,
        getWebSocketUrl,
        getHttpEndpointUrls,
    };
};
