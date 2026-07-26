// electron/main/services/obs-http-server.ts
import * as http from 'node:http';
import * as net from 'node:net';

const DEFAULT_PORT = 57321;
const DEFAULT_HOST = '127.0.0.1';

const SOURCE_PAGE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkellyCam OBS Source</title>
    <style>
        body { margin: 0; background: transparent; font-family: sans-serif; color: #fff; }
        #status { padding: 8px; font-size: 14px; }
    </style>
</head>
<body>
    <div id="status">Connecting...</div>
    <script>
        async function poll() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                document.getElementById('status').textContent = JSON.stringify(data);
            } catch (e) {
                document.getElementById('status').textContent = 'Disconnected';
            }
            setTimeout(poll, 1000);
        }
        poll();
    <\/script>
</body>
</html>`;

const CONTROL_PAGE_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkellyCam OBS Control</title>
    <style>
        body { margin: 0; padding: 16px; font-family: sans-serif; background: #1a1a1a; color: #fff; }
        button { margin: 4px; padding: 8px 16px; cursor: pointer; }
        pre { background: #333; padding: 8px; border-radius: 4px; }
    </style>
</head>
<body>
    <h2>SkellyCam OBS Control</h2>
    <div id="state">Loading...</div>
    <script>
        async function fetchState() {
            try {
                const res = await fetch('/api/state');
                const data = await res.json();
                document.getElementById('state').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '<\/pre>';
            } catch (e) {
                document.getElementById('state').textContent = 'Error: ' + e.message;
            }
        }
        fetchState();
        setInterval(fetchState, 2000);
    <\/script>
</body>
</html>`;

export class OBSHttpServer {
    private server: http.Server | null = null;
    private port: number;
    private host: string;
    private layoutConfig: Record<string, unknown> = {};

    constructor(port: number = DEFAULT_PORT, host: string = DEFAULT_HOST) {
        this.port = port;
        this.host = host;
    }

    async start(): Promise<void> {
        if (this.server) {
            return;
        }

        this.port = await this.resolvePort(this.port);

        this.server = http.createServer((req, res) => {
            this.handleRequest(req, res);
        });

        return new Promise((resolve, reject) => {
            this.server!.listen(this.port, this.host, () => {
                console.log(`[OBSHttpServer] Listening on ${this.getBaseUrl()}`);
                resolve();
            });
            this.server!.on('error', reject);
        });
    }

    async stop(): Promise<void> {
        if (!this.server) {
            return;
        }
        return new Promise((resolve, reject) => {
            this.server!.close((err) => {
                if (err) {
                    reject(err);
                } else {
                    this.server = null;
                    resolve();
                }
            });
        });
    }

    getBaseUrl(): string {
        return `http://${this.host}:${this.port}`;
    }

    getSourceUrl(): string {
        return `${this.getBaseUrl()}/source`;
    }

    getControlUrl(): string {
        return `${this.getBaseUrl()}/control`;
    }

    setLayoutConfig(config: Record<string, unknown>): void {
        this.layoutConfig = { ...config };
    }

    private handleRequest(req: http.IncomingMessage, res: http.ServerResponse): void {
        const url = req.url ?? '/';
        const method = req.method ?? 'GET';

        if (url === '/source' && method === 'GET') {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(SOURCE_PAGE_HTML);
            return;
        }

        if (url === '/control' && method === 'GET') {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(CONTROL_PAGE_HTML);
            return;
        }

        if (url === '/api/state' && method === 'GET') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok', layout: this.layoutConfig }));
            return;
        }

        if (url === '/api/config' && method === 'POST') {
            let body = '';
            req.on('data', (chunk) => { body += chunk.toString(); });
            req.on('end', () => {
                try {
                    const parsed = JSON.parse(body);
                    this.layoutConfig = { ...this.layoutConfig, ...parsed };
                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ status: 'ok', layout: this.layoutConfig }));
                } catch {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ status: 'error', message: 'Invalid JSON' }));
                }
            });
            return;
        }

        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ status: 'error', message: 'Not found' }));
    }

    private resolvePort(preferred: number): Promise<number> {
        return new Promise((resolve) => {
            const tester = net.createServer();
            tester.once('error', () => resolve(0));
            tester.once('listening', () => {
                tester.close(() => resolve(preferred));
            });
            tester.listen(preferred, this.host);
        });
    }
}

export const obsHttpServer = new OBSHttpServer();
