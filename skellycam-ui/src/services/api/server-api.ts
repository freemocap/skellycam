import { urlService } from './url-service';

class ServerApi {
    async healthCheck(signal?: AbortSignal): Promise<boolean> {
        try {
            const response = await fetch(urlService.endpoints.health, {
                signal: signal || AbortSignal.timeout(3000),
            });
            return response.ok;
        } catch {
            return false;
        }
    }

    async shutdown(): Promise<void> {
        const response = await fetch(urlService.endpoints.shutdown, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Server shutdown failed: ${response.status}`);
        }
    }
}

export const serverApi = new ServerApi();
