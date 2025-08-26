import {urlService} from "@/config/appUrlService";

export const shutdownServer = async () => {
    const url = urlService.getHttpEndpointUrls().shutdown;
    const response = await fetch(url, {method: 'GET'});

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response;
};
