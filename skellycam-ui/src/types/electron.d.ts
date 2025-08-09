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
        };
        ipcRenderer: {
            on: (channel: string, func: (...args: any[]) => void) => void;
            off: (channel: string, func: (...args: any[]) => void) => void;
            send: (channel: string, ...args: any[]) => void;
            invoke: (channel: string, ...args: any[]) => Promise<any>;
        };
        lmdbAPI: {
            get: <T>(dbName:string, key: string) => Promise<T | null>;
            put: <T>(dbName:string,key: string, value: T) => Promise<boolean>;
            remove: (dbName:string,key: string) => Promise<boolean>;
            getDbPath: () => Promise<string>;
            listKeys: (dbName: string, prefix?: string) => Promise<string[]>;
        };
    }
}

// This export is needed to make this a module
export {};
