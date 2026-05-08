import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

import './index.css'
import './i18n/i18n'

// ── React DevTools backend ─────────────────────────────────────
// Static import that runs synchronously before React mounts. The
// backend installs __REACT_DEVTOOLS_GLOBAL_HOOK__ and opens a
// WebSocket to localhost:8097 where the standalone DevTools app
// (npx react-devtools) listens.
//
// The CSP in tauri.conf.json must allow ws://127.0.0.1:* for the
// WebSocket connection to succeed — it does now.
import 'react-devtools-core/backend'

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
    <React.StrictMode>
        <App/>
    </React.StrictMode>,
)

postMessage({payload: 'removeLoading'}, '*')
