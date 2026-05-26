import * as React from 'react';
import { RecordingBrowser } from '@/components/playback/RecordingBrowser';
import { usePlaybackContext } from '@/contexts/PlaybackContext';

export const PlaybackSidebarPanel: React.FC = () => {
    const { handleRecordingLoaded, initialLoadPath } = usePlaybackContext();

    return (
        <div className="flex flex-col flex-1 bg-middark br-2 p-1 min-h-0 overflow-hidden">
            <RecordingBrowser
                onRecordingLoaded={handleRecordingLoaded}
                initialLoadPath={initialLoadPath}
            />
        </div>
    );
};
