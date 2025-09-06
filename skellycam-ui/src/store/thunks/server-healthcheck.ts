import { appUrlsService } from "@/hooks/useAppUrls";

export const serverHealthcheck = async (): Promise<Response> => {
    // Refresh config before health check to ensure we have latest URLs
    appUrlsService.refreshConfig();

    const url = appUrlsService.getHttpEndpointUrls().health;

    try {
        const response = await fetch(url, {
            method: 'GET',
            // Add timeout for health checks
            signal: AbortSignal.timeout(3000),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response;
    } catch (error) {
        // Log the actual URL that failed for debugging
        console.error(`Health check failed for ${url}:`, error);
        throw error;
    }
};
