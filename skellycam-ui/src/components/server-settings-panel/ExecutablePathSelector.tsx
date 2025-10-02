
import React, { useState, useEffect } from 'react';
import {useElectronAPI} from "@/hooks/electron-service/useElectronApi";

export const ExecutablePathSelector: React.FC = () => {
    const { api, isElectron } = useElectronAPI();
    const [candidates, setCandidates] = useState<any[]>([]);
    const [selectedPath, setSelectedPath] = useState<string | null>(null);
    const [isRunning, setIsRunning] = useState(false);

    useEffect(() => {
        if (api) {
            loadServerStatus();
        }
    }, [api]);

    const loadServerStatus = async () => {
        if (!api) return;

        try {
            const [running, path, candidateList] = await Promise.all([
                api.pythonServer.isRunning.query(),
                api.pythonServer.getExecutablePath.query(),
                api.pythonServer.getExecutableCandidates.query(),
            ]);

            setIsRunning(running);
            setSelectedPath(path);
            setCandidates(candidateList);
        } catch (error) {
            console.error('Failed to load server status:', error);
        }
    };

    const handleSelectCustom = async () => {
        if (!api) return;

        const path = await api.fileSystem.selectExecutableFile.mutate();
        if (path) {
            setSelectedPath(path);
        }
    };

    const handleStartServer = async () => {
        if (!api) return;

        try {
            await api.pythonServer.start.mutate({ exePath: selectedPath });
            await loadServerStatus();
        } catch (error) {
            console.error('Failed to start server:', error);
        }
    };

    const handleStopServer = async () => {
        if (!api) return;

        try {
            await api.pythonServer.stop.mutate();
            await loadServerStatus();
        } catch (error) {
            console.error('Failed to stop server:', error);
        }
    };

    if (!isElectron) {
        return <div>Not running in Electron</div>;
    }

    return (
        <div>
            <h3>Python Server: {isRunning ? '🟢 Running' : '🔴 Stopped'}</h3>

            <div>
                {candidates.map((candidate) => (
                    <label key={candidate.name}>
                        <input
                            type="radio"
                            value={candidate.path}
                            checked={selectedPath === candidate.path}
                            onChange={() => setSelectedPath(candidate.path)}
                            disabled={!candidate.isValid}
                        />
                        {candidate.name} - {candidate.description}
                        {!candidate.isValid && ` (${candidate.error})`}
                    </label>
                ))}
            </div>

            <button onClick={handleSelectCustom}>Browse...</button>

            {isRunning ? (
                <button onClick={handleStopServer}>Stop Server</button>
            ) : (
                <button onClick={handleStartServer}>Start Server</button>
            )}
        </div>
    );
};
