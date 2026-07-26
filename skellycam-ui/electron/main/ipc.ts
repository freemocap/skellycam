// electron/main/ipc.ts
import { ipcMain } from 'electron';
import { api } from './api';
import superjson from 'superjson';
import { buildApplicationMenu } from './services/menu-builder';
import type { MenuBuildParams } from './services/menu-builder';
import * as http from 'http';
import * as https from 'https';

export interface ServerConfig {
    mode: 'local' | 'remote';
    host: string;
    port: number;
    protocol: 'http' | 'https';
}

const DEFAULT_SERVER_CONFIG: ServerConfig = {
    mode: 'local',
    host: 'localhost',
    port: 8080,
    protocol: 'http',
};

let currentServerConfig: ServerConfig = { ...DEFAULT_SERVER_CONFIG };

function normalizeHost(raw: string): string {
    let host = raw.trim();
    host = host.replace(/^https?:\/\//i, '');
    host = host.replace(/\/+$/, '');
    return host;
}

function validateServerConfig(config: unknown): { valid: boolean; error?: string; normalized?: ServerConfig } {
    if (!config || typeof config !== 'object') {
        return { valid: false, error: 'Config must be an object' };
    }
    const c = config as Record<string, unknown>;

    if (c.mode !== 'local' && c.mode !== 'remote') {
        return { valid: false, error: 'mode must be "local" or "remote"' };
    }
    if (typeof c.host !== 'string' || c.host.trim() === '') {
        return { valid: false, error: 'host must be a non-empty string' };
    }
    if (typeof c.port !== 'number' || !Number.isInteger(c.port) || c.port < 1 || c.port > 65535) {
        return { valid: false, error: 'port must be an integer between 1 and 65535' };
    }
    if (c.protocol !== 'http' && c.protocol !== 'https') {
        return { valid: false, error: 'protocol must be "http" or "https"' };
    }

    return {
        valid: true,
        normalized: {
            mode: c.mode,
            host: normalizeHost(c.host as string),
            port: c.port as number,
            protocol: c.protocol,
        },
    };
}

function testConnection(config: ServerConfig): Promise<{ success: boolean; error?: string; latencyMs?: number }> {
    return new Promise((resolve) => {
        const start = Date.now();
        const url = `${config.protocol}://${config.host}:${config.port}/`;
        const lib = config.protocol === 'https' ? https : http;
        const req = lib.get(url, { timeout: 5000 }, (res) => {
            res.resume();
            resolve({ success: true, latencyMs: Date.now() - start });
        });
        req.on('error', (err) => {
            resolve({ success: false, error: err.message });
        });
        req.on('timeout', () => {
            req.destroy();
            resolve({ success: false, error: 'Connection timed out' });
        });
    });
}

export function setupIPC(): void {
    ipcMain.handle('trpc', async (_event, { path, input }) => {
        try {
            const caller = api.createCaller({});

            const pathParts = path.split('.');
            let current: any = caller;

            for (let i = 0; i < pathParts.length - 1; i++) {
                current = current[pathParts[i]];
                if (!current) {
                    throw new Error(`Router not found: ${pathParts.slice(0, i + 1).join('.')}`);
                }
            }

            const procedureName = pathParts[pathParts.length - 1];
            const fn = current[procedureName];

            if (typeof fn !== 'function') {
                throw new Error(`Procedure not found: ${path}`);
            }

            const result = await fn(input);
            return superjson.serialize(result);
        } catch (error) {
            console.error(`IPC Error for ${path}:`, error);
            throw error;
        }
    });

    ipcMain.handle('serverConfig.get', async () => {
        return { ...currentServerConfig };
    });

    ipcMain.handle('serverConfig.set', async (_event, config: unknown) => {
        const validation = validateServerConfig(config);
        if (!validation.valid) {
            return { success: false, error: validation.error };
        }
        currentServerConfig = validation.normalized!;
        return { success: true, config: { ...currentServerConfig } };
    });

    ipcMain.handle('serverConfig.testConnection', async (_event, config?: unknown) => {
        const target = config !== undefined ? config : currentServerConfig;
        const validation = validateServerConfig(target);
        if (!validation.valid) {
            return { success: false, error: validation.error };
        }
        return testConnection(validation.normalized!);
    });

    // Rebuild the native menu when the renderer sends translated labels
    ipcMain.on('update-menu-labels', (_event, params: MenuBuildParams) => {
        buildApplicationMenu(params);
    });
}
