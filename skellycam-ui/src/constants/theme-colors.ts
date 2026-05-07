// Single source of truth for colors shared between the theme and Electron's
// native BrowserWindow config. These mirror the CSS variables in src/styles/color.css
// but must be TypeScript constants because the Electron main process (Node.js) cannot
// read CSS files at window-creation time.
export const THEME_COLORS = {
    gray900: '#060606',
    gray800: '#1b1b1b',
    gray700: '#272727',
    gray600: '#323232',
    gray500: '#4f4f4f',
    gray400: '#9b9b9b',
    gray100: '#e4e4e4',
    green100: '#16dd12',
    green900: '#022701',
    red500: '#d7184b',
    red600: '#a01238',
    red800: '#720925',
    blue100: '#aed9f7',
    blue800: '#0898ff',
    blue900: '#083f66',
    warning500: '#e64900',
} as const;
