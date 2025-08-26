import {AppConfig} from "@/config/useAppConfig";

declare global {
    interface Window {
        electronAPI: {
            selectDirectory: () => Promise<string | null>;
            openFolder: (folderPath: string) => Promise<boolean>;
            getHomeDirectory: () => Promise<string>;
            expandPath: (path: string) => Promise<string>;
            getFolderContents: (folderPath: string) => Promise<{
                path: string;
                contents?: Array<{
                    name: string;
                    path: string;
                    isDirectory?: boolean;
                    isFile?: boolean;
                    size?: number;
                    created?: Date;
                    modified?: Date;
                    accessed?: Date;
                    error?: string;
                }>;
                error?: string;
            }>;

            getAppConfig: () => Promise<AppConfig>;
            setAppConfig: (config: any) => Promise<void>;
            getAppConfigPath: () => Promise<string>;
            onAppConfigUpdate: (callback: any) => Promise<void>
            removeAppConfigUpdateListener: (callback: any) => Promise<void>;

            startPythonServer: (exePath: string | null) => Promise<void>;
            stopPythonServer: () => Promise<void>;


            getPythonServerExecutablePath: () => Promise<string | null>;
            getPythonServerExecutableCandidates: () => Promise<ExecutableCandidate[]>;

            refreshPythonServerCandidates: () => Promise<ExecutableCandidate[]>;
            isPythonServerRunning: () => Promise<boolean>;
            getPythonServerProcessInfo: () => Promise<{ pid: number | undefined; killed: boolean } | null>;
            selectExecutableFile: () => Promise<string | null>;
        }
        ipcRenderer: {
            on: (channel: string, func: (...args: any[]) => void) => void;
            off: (channel: string, func: (...args: any[]) => void) => void;
            send: (channel: string, ...args: any[]) => void;
            invoke: (channel: string, ...args: any[]) => Promise<any>;
        }
    }
}

// This export is needed to make this a module
export {}
