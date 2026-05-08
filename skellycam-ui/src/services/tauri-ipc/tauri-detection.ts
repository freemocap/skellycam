/** Returns true if running inside a Tauri webview */
export function isTauri(): boolean {
    return typeof window !== 'undefined' && !!(window as any).__TAURI_INTERNALS__;
}
