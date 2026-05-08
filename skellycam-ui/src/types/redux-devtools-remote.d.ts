// Type declaration for @redux-devtools/remote — the package uses
// package.json "exports" which moduleResolution: "Node" can't resolve.
// This declaration suppresses the TS error; Vite handles the import fine.
declare module '@redux-devtools/remote' {
    import type { StoreEnhancer } from 'redux';

    interface DevToolsOptions {
        realtime?: boolean;
        port?: number;
        hostname?: string;
        [key: string]: unknown;
    }

    export function composeWithDevTools(
        options?: DevToolsOptions,
    ): (...enhancers: StoreEnhancer[]) => StoreEnhancer;
}
