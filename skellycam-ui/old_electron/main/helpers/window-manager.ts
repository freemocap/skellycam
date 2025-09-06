import {BrowserWindow, shell} from 'electron';
import {APP_PATHS} from "./app-paths";
import {APP_ENVIRONMENT} from "./app-environment";
import {LifecycleLogger} from "./logger";

export class WindowManager {
    static createMainWindow() {
        const window = new BrowserWindow({
            title: 'Skellycam 💀📸',
            icon: APP_PATHS.SKELLYCAM_ICON_PATH,
            width: 1280,
            height: 720,
            webPreferences: {
                preload: APP_PATHS.PRELOAD,
                contextIsolation: true,
                nodeIntegration: false
            }
        });

        this.configureWindowHandlers(window);
        this.loadContent(window);
        LifecycleLogger.logWindowCreation(window);
        return window;
    }

    private static configureWindowHandlers(window: BrowserWindow) {
        console.log('Configuring window handlers');
        window.on('closed', () => {
            console.log('Window closed');
        });
        window.webContents.on('did-finish-load', () => {
            console.log('Window finished loading');
            window.webContents.send('app-ready', Date.now());
        });


        // Intercept navigation to external links (for regular link clicks)
        window.webContents.on('will-navigate', (event, url) => {
            // Prevent navigation to external URLs and open them in default browser
            if (url.startsWith('http:') || url.startsWith('https:')) {
                event.preventDefault();
                shell.openExternal(url).then(r => console.log('External link opened via navigation:', url)).catch(err => console.error('Failed to open external link via navigation:', err));
            }
        });

    }

    private static loadContent(window: BrowserWindow) {
        console.log('Loading app content - APP_ENVIRONMENT.IS_DEV:', APP_ENVIRONMENT.IS_DEV);

        APP_ENVIRONMENT.IS_DEV
            ? window.loadURL(process.env.VITE_DEV_SERVER_URL!)
            : window.loadFile(APP_PATHS.RENDERER_HTML);


    }

}
