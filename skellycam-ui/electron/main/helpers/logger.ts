import { app, BrowserWindow } from 'electron';
import { ENV_CONFIG } from './constants';

export class LifecycleLogger {
  static logProcessInfo() {
    console.log(`
    ============================================
    Starting SkellyCam v${app.getVersion()}
    Environment: ${ENV_CONFIG.IS_DEV ? 'Development' : 'Production'}
    Platform: ${process.platform}-${process.arch}
    Node: ${process.versions.node}
    Chrome: ${process.versions.chrome}
    Electron: ${process.versions.electron}
    Python Auto-Start: ${ENV_CONFIG.SHOULD_LAUNCH_PYTHON}
    ============================================`);
  }

  static logWindowCreation(win: BrowserWindow) {
    console.log(`
    [Window Manager] Created main window
    ├── ID: ${win.id}
    ├── DevTools: ${ENV_CONFIG.IS_DEV ? 'Open' : 'Closed'}
    └── Load URL: ${win.webContents.getURL()}`);
  }

  static logPythonProcess(pid: number) {
    console.log(`
    [Python Server] Started external process
    ├── PID: ${pid}
    ├── Path: ${process.env.SKELLYCAM_PYTHON_PATH}
    └── Environment: ${JSON.stringify(process.env, null, 2)}`);
  }

  static logIpcEvent(channel: string, sender: string) {
    console.log(`
    [IPC Event] ${new Date().toISOString()}
    ├── Channel: ${channel}
    └── Origin: ${sender}`);
  }

  static logShutdownSequence() {
    console.log(`
    [Shutdown] Initiating termination sequence
    ├── Windows open: ${BrowserWindow.getAllWindows().length}
    ├── Python running: ${process.env.SKELLYCAM_SHOULD_SHUTDOWN === 'true' ? 'No' : 'Yes'}
    └── Reason: Application closure requested`);
  }
}