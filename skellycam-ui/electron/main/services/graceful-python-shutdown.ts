import type {ChildProcess} from 'node:child_process';

/** Wait for Python to finalize recordings; never substitute a process-tree kill. */
export async function gracefulPythonShutdown(
    child: ChildProcess,
    shutdownUrl: string,
    request: typeof fetch = fetch,
): Promise<void> {
    const exited = () => child.exitCode !== null || child.signalCode !== null;
    if (exited()) return;
    let onExit: () => void = () => {};
    const exit = new Promise<void>(resolve => { onExit = resolve; });
    child.once('exit', onExit);
    try {
        try {
            const response = await request(shutdownUrl, {signal: AbortSignal.timeout(5000)});
            if (!response.ok) throw new Error(`Shutdown request failed: HTTP ${response.status}`);
        } catch (error) {
            if (!exited()) {
                throw new Error(`Python was left running to protect active video saves. Retry graceful shutdown: ${String(error)}`);
            }
        }
        // An HTTP acknowledgement is not a save-complete acknowledgement.
        if (!exited()) await exit;
    } finally {
        child.removeListener('exit', onExit);
    }
}
