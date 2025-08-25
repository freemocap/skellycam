import {useAppConfig} from "@/config/useAppConfig";
import {urlService} from "@/config/appUrlService";

export const pauseUnpauseThunk = async () => {
        const pauseUnpauseUrl = urlService.getHttpEndpointUrls().pauseUnpauseCameras;
        await fetch(
                pauseUnpauseUrl,{method: 'GET'}
        );
    };

