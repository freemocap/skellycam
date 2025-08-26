import {urlService} from "@/config/appUrlService";

export const serverHealthcheck = async () => {
    const url = urlService.getHttpEndpointUrls().health;
    const response = await fetch(url, {method: 'GET'});

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response;
};
