import React, {createContext, useContext, useEffect, useState} from "react";
import {useAppDispatch, useAppSelector} from "@/store";
import {
    StartStopRecordingButton
} from "@/components/recording-info-panel/recording-subcomponents/StartStopRecordingButton";
import {
    MicrophoneSelector
} from "@/components/recording-info-panel/recording-subcomponents/MicrophoneSelector";
import {startRecording, stopRecording, recordingInfoUpdated} from "@/store";
import {useElectronIPC} from "@/services/electron-ipc/electron-ipc";
import {useServer} from "@/services/server/ServerContextProvider";
import {getTimestampString} from "@/components/recording-info-panel/getTimestampString";
import {RecordingCompleteDialog} from "@/components/recording-info-panel/RecordingCompleteDialog";
import {RecordingPathModal} from "@/components/recording-info-panel/RecordingPathModal";
import ButtonSm from "@/components/ui-components/ButtonSm";
import { useTranslation } from "react-i18next";

interface RecordingOperation {
    type: 'start' | 'stop';
    timestamp: number;
}

interface RecordingPanelContextType {
    createSubfolder: boolean;
    setCreateSubfolder: (v: boolean) => void;
    useDelayStart: boolean;
    setUseDelayStart: (v: boolean) => void;
    delaySeconds: number;
    setDelaySeconds: (v: number) => void;
    countdown: number | null;
    pendingOperation: RecordingOperation | null;
    recordingStartTime: number | null;
    useTimestamp: boolean;
    setUseTimestamp: (v: boolean) => void;
    useIncrement: boolean;
    setUseIncrement: (v: boolean) => void;
    currentIncrement: number;
    setCurrentIncrement: (v: number) => void;
    baseName: string;
    setBaseName: (v: string) => void;
    customSubfolderName: string;
    setCustomSubfolderName: (v: string) => void;
    recordingTag: string;
    setRecordingTag: (v: string) => void;
    micDeviceIndex: number;
    setMicDeviceIndex: (v: number) => void;
    pathModalOpen: boolean;
    setPathModalOpen: (v: boolean) => void;
    microphoneError: string | null;
    setMicrophoneError: (v: string | null) => void;
    recordingName: string;
    subfolderName: string | undefined;
    displayPath: string;
    noCamerasConnected: boolean;
    isRecording: boolean;
    recordingDirectory: string;
    handleRecordButtonClick: () => Promise<void>;
}

const RecordingPanelContext = createContext<RecordingPanelContextType | null>(null);

const useRecordingPanel = (): RecordingPanelContextType => {
    const ctx = useContext(RecordingPanelContext);
    if (!ctx) throw new Error("useRecordingPanel must be used within RecordingPanelProvider");
    return ctx;
};

export const RecordingPanelProvider: React.FC<{children: React.ReactNode}> = ({children}) => {
    const dispatch = useAppDispatch();
    const recordingInfo = useAppSelector((state) => state.recording);

    const [createSubfolder, setCreateSubfolder] = useState<boolean>(false);
    const [useDelayStart, setUseDelayStart] = useState<boolean>(false);
    const [delaySeconds, setDelaySeconds] = useState<number>(3);
    const [countdown, setCountdown] = useState<number | null>(null);
    const [pendingOperation, setPendingOperation] = useState<RecordingOperation | null>(null);
    const [recordingStartTime, setRecordingStartTime] = useState<number | null>(null);
    const [useTimestamp, setUseTimestamp] = useState<boolean>(true);
    const [useIncrement, setUseIncrement] = useState<boolean>(false);
    const [currentIncrement, setCurrentIncrement] = useState<number>(1);
    const [baseName, setBaseName] = useState<string>("recording");
    const [customSubfolderName, setCustomSubfolderName] = useState<string>("");
    const [recordingTag, setRecordingTag] = useState<string>("");
    const [micDeviceIndex, setMicDeviceIndex] = useState<number>(-1);
    const [pathModalOpen, setPathModalOpen] = useState<boolean>(false);

    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();
    const noCamerasConnected = connectedCameraIds.length === 0;

    useEffect(() => {
        if (pendingOperation) {
            const isNowRecording = recordingInfo.isRecording;
            const wasStarting = pendingOperation.type === 'start';
            const wasStopping = pendingOperation.type === 'stop';
            if ((wasStarting && isNowRecording) || (wasStopping && !isNowRecording)) {
                setPendingOperation(null);
                if (wasStarting && isNowRecording) setRecordingStartTime(Date.now());
                else if (wasStopping && !isNowRecording) setRecordingStartTime(null);
            }
            if (Date.now() - pendingOperation.timestamp > 5000) {
                console.error(`Recording ${pendingOperation.type} timed out`);
                setPendingOperation(null);
            }
        }
    }, [recordingInfo.isRecording, pendingOperation]);

    useEffect(() => {
        if (recordingInfo.isRecording && !recordingStartTime) setRecordingStartTime(Date.now());
    }, []);

    useEffect(() => {
        if (recordingInfo?.recordingDirectory?.startsWith("~") && isElectron && api) {
            api.fileSystem.getHomeDirectory.query()
                .then((homePath: string) => {
                    const updated = recordingInfo.recordingDirectory.replace("~", homePath).replace(/\\/g, "/");
                    dispatch(recordingInfoUpdated({recordingDirectory: updated}));
                })
                .catch((error: unknown) => { console.error("Failed to get home directory:", error); throw error; });
        }
    }, [recordingInfo.recordingDirectory, isElectron, api, dispatch]);

    useEffect(() => {
        if (countdown !== null && countdown > 0) {
            const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
            return () => clearTimeout(timer);
        } else if (countdown === 0) {
            handleStartRecording();
            setCountdown(null);
        }
    }, [countdown]);

    const buildRecordingName = (): string => {
        const parts: string[] = [];
        if (useTimestamp) parts.push(getTimestampString());
        else parts.push(baseName);
        if (recordingTag) parts.push(recordingTag);
        return parts.join("_");
    };

    const handleStartRecording = async (): Promise<void> => {
        const recordingName = buildRecordingName();
        const subfolderName = createSubfolder ? (customSubfolderName || getTimestampString()) : "";
        const recordingPath = createSubfolder
            ? `${recordingInfo.recordingDirectory}/${subfolderName}`
            : recordingInfo.recordingDirectory;
        if (useIncrement) setCurrentIncrement((prev) => prev + 1);
        setPendingOperation({ type: 'start', timestamp: Date.now() });
        try {
            await dispatch(startRecording({ recordingName, recordingDirectory: recordingPath, micDeviceIndex })).unwrap();
        } catch (error) {
            console.error("Failed to start recording:", error);
            setPendingOperation(null);
            throw error;
        }
    };

    const handleRecordButtonClick = async (): Promise<void> => {
        if (pendingOperation) return;
        if (recordingInfo.isRecording) {
            setPendingOperation({ type: 'stop', timestamp: Date.now() });
            try {
                await dispatch(stopRecording()).unwrap();
            } catch (error) {
                console.error("Failed to stop recording:", error);
                setPendingOperation(null);
                throw error;
            }
        } else if (useDelayStart) {
            setCountdown(delaySeconds);
        } else {
            await handleStartRecording();
        }
    };

    const recordingName = buildRecordingName() + (useIncrement ? `_${currentIncrement}` : '');
    const subfolderName = createSubfolder ? (customSubfolderName || undefined) : undefined;
    const displayPath = (createSubfolder && customSubfolderName)
        ? `${recordingInfo.recordingDirectory}/${customSubfolderName}/${recordingName}`
        : `${recordingInfo.recordingDirectory}/${recordingName}`;

    return (
        <RecordingPanelContext.Provider value={{
            createSubfolder, setCreateSubfolder,
            useDelayStart, setUseDelayStart,
            delaySeconds, setDelaySeconds,
            countdown,
            pendingOperation,
            recordingStartTime,
            useTimestamp, setUseTimestamp,
            useIncrement, setUseIncrement,
            currentIncrement, setCurrentIncrement,
            baseName, setBaseName,
            customSubfolderName, setCustomSubfolderName,
            recordingTag, setRecordingTag,
            micDeviceIndex, setMicDeviceIndex,
            pathModalOpen, setPathModalOpen,
            microphoneError, setMicrophoneError,
            recordingName,
            subfolderName,
            displayPath,
            noCamerasConnected,
            isRecording: recordingInfo.isRecording,
            recordingDirectory: recordingInfo.recordingDirectory,
            handleRecordButtonClick,
        }}>
            {children}
        </RecordingPanelContext.Provider>
    );
};

export const RecordingOptionsPanel: React.FC = () => {
    const {
        displayPath, pathModalOpen, setPathModalOpen, microphoneError,
        recordingDirectory, recordingName, subfolderName, countdown,
        recordingTag, useDelayStart, delaySeconds, useTimestamp, baseName,
        useIncrement, currentIncrement, createSubfolder, customSubfolderName,
        isRecording, setUseDelayStart, setDelaySeconds, setRecordingTag,
        setUseTimestamp, setBaseName, setUseIncrement, setCurrentIncrement,
        setCreateSubfolder, setCustomSubfolderName,
    } = useRecordingPanel();

    return (
        <div className="main-side-actions flex flex-col gap-1 z-3" style={{flexShrink: 0}}>
            <div className="pos-rel file-directory-group bg-middark br-2 p-1 flex flex-col gap-1 br-1 p-1 pb-2">
                <p className="text-nowrap text-left bg-md text-darkgray p-1">File directory</p>
                <div className="button-sm-group gap-1 br-1 button items-center sm fit-content flex-inline text-left items-center text-black full-width" style={{pointerEvents: "none"}}>
                    <span className="icon icon-size-20 subfolder-icon" />
                    <p className="text-gray text-nowrap text md text-align-left flex flex-end">
                        {displayPath || "Set recording path"}
                    </p>
                </div>
                <ButtonSm
                    iconClass="settings-icon"
                    text="Recording Options"
                    textColor="text-gray"
                    buttonType="full-width"
                    onClick={() => setPathModalOpen(true)}
                />
                <RecordingCompleteDialog />
                <RecordingPathModal
                    open={pathModalOpen}
                    onClose={() => setPathModalOpen(false)}
                    recordingDirectory={recordingDirectory}
                    recordingName={recordingName}
                    subfolder={subfolderName}
                    countdown={countdown}
                    recordingTag={recordingTag}
                    useDelayStart={useDelayStart}
                    delaySeconds={delaySeconds}
                    useTimestamp={useTimestamp}
                    baseName={baseName}
                    useIncrement={useIncrement}
                    currentIncrement={currentIncrement}
                    createSubfolder={createSubfolder}
                    customSubfolderName={customSubfolderName}
                    isRecording={isRecording}
                    onDelayToggle={setUseDelayStart}
                    onDelayChange={setDelaySeconds}
                    onTagChange={setRecordingTag}
                    onNameChange={(value) => { setUseTimestamp(false); setBaseName(value); }}
                    onUseTimestampChange={setUseTimestamp}
                    onBaseNameChange={setBaseName}
                    onUseIncrementChange={setUseIncrement}
                    onIncrementChange={setCurrentIncrement}
                    onCreateSubfolderChange={setCreateSubfolder}
                    onCustomSubfolderNameChange={setCustomSubfolderName}
                />
            </div>
        </div>
    );
};

export const RecordingButtonPanel: React.FC = () => {
    const { t } = useTranslation();
    const {
        isRecording, pendingOperation, countdown, recordingStartTime,
        noCamerasConnected, micDeviceIndex, setMicDeviceIndex, setMicrophoneError,
        handleRecordButtonClick,
    } = useRecordingPanel();

    return (
        <div className="main-side-actions flex flex-col gap-1 z-3" style={{flexShrink: 0}}>
            <div className="record-group bg-middark br-2 p-1 flex flex-col gap-1 br-1 p-2 pb-2">
                <div className="flex flex-row flex-1 items-center gap-1 fit-content w-full min-w-full" onClick={(e) => e.stopPropagation()} onMouseDown={(e) => e.stopPropagation()}>
                    <StartStopRecordingButton
                        isRecording={isRecording}
                        isPending={pendingOperation !== null}
                        countdown={countdown}
                        recordingStartTime={recordingStartTime}
                        disabled={noCamerasConnected && !isRecording}
                        tooltipText={noCamerasConnected && !isRecording ? t('connectCamerasToRecord') : undefined}
                        onClick={handleRecordButtonClick}
                    />
                </div>
                <MicrophoneSelector
                    selectedMicIndex={micDeviceIndex}
                    onMicSelected={setMicDeviceIndex}
                    disabled={isRecording}
                    onError={setMicrophoneError}
                />
            </div>
                    
            {/* Microphone */}
            <MicrophoneSelector
                selectedMicIndex={micDeviceIndex}
                onMicSelected={setMicDeviceIndex}
                disabled={recordingInfo.isRecording}
            />
        </div>
    );
};

export const RecordingInfoPanel: React.FC = () => (
    <RecordingPanelProvider>
        <RecordingOptionsPanel />
        <RecordingButtonPanel />
    </RecordingPanelProvider>
);
