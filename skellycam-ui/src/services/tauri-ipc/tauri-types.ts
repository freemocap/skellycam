// Type definitions for Tauri IPC — mirrors the Rust structs

export interface ExecutableCandidate {
    name: string;
    path: string;
    description: string;
    isValid?: boolean;
    error?: string;
    resolvedPath?: string;
}

export interface ProcessInfo {
    pid: number | null;
    killed: boolean;
}

export interface FolderEntry {
    name: string;
    path: string;
    isDirectory: boolean;
    isFile: boolean;
    size: number;
    modified: number; // milliseconds since epoch
}

export interface FetchOptions {
    url: string;
    method?: string;
    headers?: Record<string, string>;
    body?: string;
}

export interface FetchResponse {
    ok: boolean;
    status: number;
    statusText: string;
    data: string;
}
