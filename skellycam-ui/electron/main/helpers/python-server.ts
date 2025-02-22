import {exec} from 'child_process';
import fs from 'node:fs';
import {LifecycleLogger} from "./logger";
import {APP_PATHS} from "./app-paths";

let pythonProcess: ReturnType<typeof exec> | null = null;

export class PythonServer {
    static async start() {
        console.log('Starting python server subprocess');
        this.validateExecutable();

        pythonProcess = exec(`"${APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH}"`, {
            env: {
                ...process.env,
                PYTHONIOENCODING: 'utf-8',
                PYTHONUTF8: '1'
            },
            maxBuffer: 1024 * 1024
        });

        pythonProcess.stdout?.on('data', (data) =>
            console.log(`[Python] ${data}`));

        pythonProcess.stderr?.on('data', (data) =>
            console.error(`[Python Error] ${data}`));

        pythonProcess.on('exit', (code) => {
            console.log(`Python exited (code: ${code})`);
        });
        if (!pythonProcess.pid) throw new Error('Python server failed to start!');
        LifecycleLogger.logPythonProcess(pythonProcess);

    }

    static async shutdown() {
        if (!pythonProcess) return;
        console.log('Shutting down python server - setting env variable `SKELLYCAM_SHOULD_SHUTDOWN` to `true`');
        process.env.SKELLYCAM_SHOULD_SHUTDOWN = 'true';
        let shutdownTimer = 0;

        while (pythonProcess && !pythonProcess.exitCode && shutdownTimer < 10) {
            await new Promise(r => setTimeout(r, 1000));
            shutdownTimer++;
            console.log(`Waiting for python process to close for ${shutdownTimer}`)
        }

        if (pythonProcess && !pythonProcess.exitCode) {
            console.warn('Python server did not shut down gracefully - killing sub-process')
            pythonProcess.kill();
            pythonProcess = null;
        } else {
            console.log('Python server shut down with exit code:', pythonProcess.exitCode);
        }
    }

    private static validateExecutable() {
        console.log('Validating python server executable...');
        const checkPath = (path: string) => {
            if (!fs.existsSync(path)) throw new Error(`Missing Python server at ${path}`);
            console.log(`✓ Found python server executable at: ${path}`);
            try {
                fs.accessSync(path, fs.constants.X_OK);
                console.log(`✓ Executable check passed for: ${path}`);
            } catch (error) {
                throw new Error(`✗ File not executable: ${path}\n   Details: ${error}`);
            }
        };

        try {
            checkPath(APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH);
        } catch {
            checkPath(APP_PATHS.PYTHON_SERVER_EXECUTABLE_DEV);
            APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH = APP_PATHS.PYTHON_SERVER_EXECUTABLE_DEV;
        }
        console.log(`Using python server executable at ${APP_PATHS.PYTHON_SERVER_EXECUTABLE_PATH}`);

    }
}
