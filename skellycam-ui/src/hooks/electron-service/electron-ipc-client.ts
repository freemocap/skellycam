// src/hooks/electron-service/electron-ipc-link.ts
import { createTRPCProxyClient } from '@trpc/client';
import superjson from 'superjson';
import type { AppAPI } from '../../../electron/main/api';

// Type for the electron API exposed via preload
interface ElectronAPI {
    invoke: (path: string, input?: any) => Promise<any>;
}

declare global {
    interface Window {
        electronAPI: ElectronAPI;
    }
}

// Custom link for Electron IPC
const createElectronLink = () => {
    return () => {
        return ({ op }: any) => {
            return {
                subscribe: (observer: {
                    next: (value: any) => void;
                    error: (error: any) => void;
                    complete: () => void;
                }) => {
                    const execute = async () => {
                        try {
                            // Check if electronAPI is available
                            if (!window.electronAPI) {
                                throw new Error('Electron API not available');
                            }

                            // Call through the IPC bridge
                            const serializedResult = await window.electronAPI.invoke(
                                op.path,
                                op.input
                            );

                            // Deserialize the result
                            const result = superjson.deserialize(serializedResult);

                            observer.next({
                                result: {
                                    type: 'data',
                                    data: result,
                                },
                            });
                            observer.complete();
                        } catch (error) {
                            console.error(`IPC Error for ${op.path}:`, error);
                            observer.error(
                                error instanceof Error
                                    ? error
                                    : new Error(String(error))
                            );
                        }
                    };

                    // Execute the request
                    execute();

                    // Return unsubscribe function
                    return {
                        unsubscribe: () => {
                            // No-op for now, but could be used for cancellation
                        },
                    };
                },
            };
        };
    };
};

// Create the typed client
export const electronIpcClient = createTRPCProxyClient<AppAPI>({
    links: [createElectronLink()],
    transformer: superjson,
});

// Helper to check if running in Electron
export const isElectron = (): boolean => {
    return typeof window !== 'undefined' && !!window.electronAPI;
};
