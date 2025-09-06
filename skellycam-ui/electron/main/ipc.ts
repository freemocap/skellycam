// electron/main/ipc.ts
import { ipcMain } from 'electron';
import { api } from './api';
import superjson from 'superjson';

export function setupIPC(): void {
    ipcMain.handle('trpc', async (_event, { path, input }) => {
        try {
            // Split the path to get router and procedure names
            const pathParts = path.split('.');
            let currentRouter: any = api;

            // Navigate through the router path
            for (let i = 0; i < pathParts.length - 1; i++) {
                currentRouter = currentRouter[pathParts[i]];
                if (!currentRouter) {
                    throw new Error(`Router not found: ${pathParts.slice(0, i + 1).join('.')}`);
                }
            }

            // Get the procedure
            const procedureName = pathParts[pathParts.length - 1];
            const procedure = currentRouter[procedureName];

            if (!procedure) {
                throw new Error(`Procedure not found: ${path}`);
            }

            // Call the procedure
            const result = await procedure({ input, ctx: {} });

            // Serialize the result using superjson
            return superjson.serialize(result);
        } catch (error) {
            console.error(`IPC Error for ${path}:`, error);
            throw error;
        }
    });
}
