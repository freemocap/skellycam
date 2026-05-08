import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
    const isServe = command === 'serve'
    const sourcemap = isServe || !!process.env.VSCODE_DEBUG

    return {
        resolve: {
            alias: {
                '@': path.join(__dirname, 'src')
            },
        },
        plugins: [
            react(),
        ],
        optimizeDeps: {},
        server: {
            host: '127.0.0.1',
            port: 7777,
            strictPort: true,
            headers: {
                "Cross-Origin-Opener-Policy": "same-origin",
                "Cross-Origin-Embedder-Policy": "require-corp",
            },
        },
        build: {
            sourcemap,
            outDir: 'dist',
        },
        clearScreen: false,
    }
})
