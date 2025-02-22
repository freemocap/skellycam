
import { app } from 'electron';
import os from 'node:os';

export function configureApp() {
  // Environment defaults
  process.env.SKELLYCAM_RUNNING_IN_ELECTRON = 'true';
  process.env.SKELLYCAM_SHOULD_SHUTDOWN = 'false';

  // Platform config
// Disable GPU Acceleration for Windows 7
if (os.release().startsWith('6.1')) app.disableHardwareAcceleration()
  if (process.platform === 'win32') app.setAppUserModelId(app.getName());
}