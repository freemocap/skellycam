import { Menu, MenuItem, Submenu, PredefinedMenuItem } from '@tauri-apps/api/menu';
import { isTauri } from '@/services/tauri-ipc/tauri-detection';

export type MenuAction =
    | 'navigate-home'
    | 'navigate-cameras'
    | 'navigate-playback'
    | 'navigate-settings'
    | 'toggle-theme'
    | 'toggle-sidebar'
    | 'detect-cameras'
    | 'connect-cameras'
    | 'close-cameras'
    | 'pause-unpause-cameras'
    | 'start-recording'
    | 'stop-recording'
    | 'open-recording-folder'
    | 'toggle-fullscreen'
    | 'toggle-locale'
    | 'check-for-updates'
    | `change-locale:${string}`;

export interface LocaleEntry {
    code: string;
    label: string;
}

export interface MenuLabels {
    menuFile: string; menuView: string; menuCamera: string; menuRecording: string;
    menuHelp: string; menuDetectCameras: string; menuConnectCameras: string;
    menuCloseAllCameras: string; menuOpenRecordingFolder: string;
    menuToggleSidebar: string; menuToggleTheme: string; menuToggleFullScreen: string;
    menuPauseUnpause: string; menuConnectApplySettings: string; menuCloseAll: string;
    menuDocumentation: string; menuGitHubRepository: string; menuReportIssue: string;
    menuAbout: string; menuCheckForUpdates: string; menuPlayback: string;
    home: string; cameras: string; settings: string;
    startRecording: string; stopRecording: string; language: string;
}

const DEFAULT_LABELS: MenuLabels = {
    menuFile: 'File', menuView: 'View', menuCamera: 'Camera',
    menuRecording: 'Recording', menuHelp: 'Help',
    menuDetectCameras: 'Detect Cameras', menuConnectCameras: 'Connect Cameras',
    menuCloseAllCameras: 'Close All Cameras',
    menuOpenRecordingFolder: 'Open Recording Folder…',
    menuToggleSidebar: 'Toggle Sidebar', menuToggleTheme: 'Toggle Theme',
    menuToggleFullScreen: 'Toggle Full Screen',
    menuPauseUnpause: 'Pause / Unpause',
    menuConnectApplySettings: 'Connect / Apply Settings', menuCloseAll: 'Close All',
    menuDocumentation: 'Documentation', menuGitHubRepository: 'GitHub Repository',
    menuReportIssue: 'Report an Issue…', menuAbout: 'About SkellyCam',
    menuCheckForUpdates: 'Check for Updates…', menuPlayback: 'Playback',
    home: 'Home', cameras: 'Cameras', settings: 'Settings',
    startRecording: 'Start Recording', stopRecording: 'Stop Recording',
    language: 'Language',
};

function dispatchMenuAction(action: MenuAction) {
    window.dispatchEvent(new CustomEvent('menu-action', { detail: action }));
}

type AnyMenuItem = MenuItem | PredefinedMenuItem;

async function mi(text: string, action: () => void, accelerator?: string): Promise<MenuItem> {
    return await MenuItem.new({ text, accelerator, action });
}

async function sep(): Promise<PredefinedMenuItem> {
    return await PredefinedMenuItem.new({ item: 'Separator' });
}

export interface MenuBuildParams {
    labels?: Partial<MenuLabels>;
    locales?: LocaleEntry[];
    currentLocale?: string;
    onMenuAction?: (action: MenuAction) => void;
}

export async function buildApplicationMenu(
    params: MenuBuildParams = {},
): Promise<void> {
    if (!isTauri()) return;

    const { labels, locales = [], currentLocale = 'en', onMenuAction } = params;
    const t: MenuLabels = { ...DEFAULT_LABELS, ...labels };

    if (onMenuAction) {
        const handler = (e: Event) => {
            onMenuAction((e as CustomEvent).detail as MenuAction);
        };
        window.removeEventListener('menu-action', handler);
        window.addEventListener('menu-action', handler);
    }

    const isMac = navigator.platform?.toLowerCase().includes('mac') ?? false;

    // Build language submenu items
    const langItems: AnyMenuItem[] = [
        await mi('Toggle Language', () => dispatchMenuAction('toggle-locale'), 'CmdOrCtrl+Shift+L'),
        await sep(),
    ];
    for (const locale of locales) {
        langItems.push(
            await mi(locale.label, () =>
                dispatchMenuAction(`change-locale:${locale.code}`),
            ),
        );
    }

    // File menu
    const fileItems: AnyMenuItem[] = [
        await mi(t.menuOpenRecordingFolder, () => dispatchMenuAction('open-recording-folder'), 'CmdOrCtrl+O'),
        await sep(),
        await Submenu.new({ text: t.language, items: langItems }),
        await mi(`${t.settings}…`, () => dispatchMenuAction('navigate-settings'), 'CmdOrCtrl+,'),
        await sep(),
        isMac
            ? await PredefinedMenuItem.new({ item: 'CloseWindow' })
            : await PredefinedMenuItem.new({ item: 'Quit' }),
    ];

    // View menu
    const viewItems: AnyMenuItem[] = [
        await mi(t.home, () => dispatchMenuAction('navigate-home'), 'CmdOrCtrl+1'),
        await mi(t.cameras, () => dispatchMenuAction('navigate-cameras'), 'CmdOrCtrl+2'),
        await mi(t.menuPlayback, () => dispatchMenuAction('navigate-playback'), 'CmdOrCtrl+3'),
        await sep(),
        await mi(t.menuToggleSidebar, () => dispatchMenuAction('toggle-sidebar'), 'CmdOrCtrl+B'),
        await mi(t.menuToggleTheme, () => dispatchMenuAction('toggle-theme'), 'CmdOrCtrl+Shift+T'),
        await sep(),
        await mi(t.menuToggleFullScreen, () => dispatchMenuAction('toggle-fullscreen'), isMac ? 'Ctrl+Cmd+F' : 'F11'),
    ];

    // Camera menu
    const cameraItems: AnyMenuItem[] = [
        await mi(t.menuDetectCameras, () => dispatchMenuAction('detect-cameras'), 'CmdOrCtrl+D'),
        await mi(t.menuConnectApplySettings, () => dispatchMenuAction('connect-cameras'), 'CmdOrCtrl+Shift+C'),
        await mi(t.menuCloseAll, () => dispatchMenuAction('close-cameras'), 'CmdOrCtrl+Shift+W'),
        await sep(),
        await mi(t.menuPauseUnpause, () => dispatchMenuAction('pause-unpause-cameras'), 'Shift+Space'),
    ];

    // Recording menu
    const recordingItems: AnyMenuItem[] = [
        await mi(t.startRecording, () => dispatchMenuAction('start-recording'), 'CmdOrCtrl+Shift+S'),
        await mi(t.stopRecording, () => dispatchMenuAction('stop-recording'), 'CmdOrCtrl+Shift+X'),
        await sep(),
        await mi(t.menuOpenRecordingFolder, () => dispatchMenuAction('open-recording-folder')),
    ];

    // Help menu
    const helpItems: AnyMenuItem[] = [
        await mi(t.menuDocumentation, () => window.open('https://docs.freemocap.org/skellycam', '_blank')),
        await mi(t.menuGitHubRepository, () => window.open('https://github.com/freemocap/skellycam', '_blank')),
        await mi(t.menuReportIssue, () => window.open('https://github.com/freemocap/skellycam/issues/new', '_blank')),
        await sep(),
        await mi('FreeMoCap Foundation', () => window.open('https://freemocap.org', '_blank')),
        await sep(),
        await mi(t.menuCheckForUpdates, () => dispatchMenuAction('check-for-updates')),
        await sep(),
        await mi(t.menuAbout, () => dispatchMenuAction('navigate-settings')),
    ];

    const submenus: Submenu[] = [];

    if (isMac) {
        submenus.push(
            await Submenu.new({
                text: 'Skellycam',
                items: [
                    await mi(`About ${t.menuAbout}`, () => dispatchMenuAction('navigate-settings')),
                    await sep(),
                    await mi(`${t.settings}…`, () => dispatchMenuAction('navigate-settings'), 'Cmd+,'),
                    await sep(),
                    await PredefinedMenuItem.new({ item: 'Services' }),
                    await sep(),
                    await PredefinedMenuItem.new({ item: 'Hide' }),
                    await PredefinedMenuItem.new({ item: 'HideOthers' }),
                    await PredefinedMenuItem.new({ item: 'ShowAll' }),
                    await sep(),
                    await PredefinedMenuItem.new({ item: 'Quit' }),
                ],
            }),
        );
    }

    submenus.push(await Submenu.new({ text: t.menuFile, items: fileItems }));
    submenus.push(await Submenu.new({ text: t.menuView, items: viewItems }));
    submenus.push(await Submenu.new({ text: t.menuCamera, items: cameraItems }));
    submenus.push(await Submenu.new({ text: t.menuRecording, items: recordingItems }));

    if (isMac) {
        submenus.push(
            await Submenu.new({
                text: 'Window',
                items: [
                    await PredefinedMenuItem.new({ item: 'Minimize' }),
                    await PredefinedMenuItem.new({ item: 'Maximize' }),
                    await sep(),
                    await PredefinedMenuItem.new({ item: 'BringAllToFront' }),
                ],
            }),
        );
    }

    submenus.push(await Submenu.new({ text: t.menuHelp, items: helpItems }));

    const menu = await Menu.new({ items: submenus });
    await menu.setAsAppMenu();
}
