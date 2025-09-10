// store/middleware/connection-middleware.ts
import { Middleware } from '@reduxjs/toolkit';
import { autoConnect } from '@/store/slices/server';

interface ServerConfig {
    autoSpawn: boolean;
    autoConnect: boolean;
}

interface StateWithServer {
    server: {
        config: ServerConfig;
    };
}

/**
 * Middleware to handle automatic connection on app startup
 */
export const connectionMiddleware: Middleware<{}, StateWithServer> = (store) => {
    // Flag to track if we've initialized
    let isInitialized = false;

    return (next) => (action) => {
        // Process the action first
        const result = next(action);

        // Check if this is an action with a type property
        if (!isInitialized && typeof action === 'object' && action !== null && 'type' in action) {
            const actionWithType = action as { type: string };

            // After the store is ready and on the first action, trigger auto-connect
            if (actionWithType.type === '@@INIT') {
                isInitialized = true;

                // Defer auto-connect to next tick to ensure store is fully ready
                setTimeout(() => {
                    const state = store.getState() as StateWithServer;
                    const { autoSpawn, autoConnect: shouldAutoConnect } = state.server.config;

                    if (autoSpawn || shouldAutoConnect) {
                        console.log('Auto-connecting based on configuration');
                        store.dispatch(autoConnect() as any);
                    }
                }, 0);
            }
        }

        return result;
    };
};
