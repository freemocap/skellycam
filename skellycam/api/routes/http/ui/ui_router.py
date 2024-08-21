from fastapi import APIRouter
from starlette.responses import HTMLResponse

UI_HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkellyCam API Tester with WebSocket</title>
    <style>
        .smol-image {
            width: 640px;
            height: auto;
        }
        div {
            background-color: #654a7b;
        }
        h1 {
            font-size: 24px;
        }
        button {
            margin-right: 10px;
            padding: 10px;
            font-size: small;
        }
    </style>
    <script>
        let ws;
        let isConnected = false;
        const latestImages = {};

        function updateStatus() {
            document.getElementById('ws-status').innerText = isConnected ? 'Connected' : 'Disconnected';
        }

        function connectWebSocket() {
            ws = new WebSocket('ws://localhost:8000/ws/connect');
            ws.onopen = () => {
                isConnected = true;
                updateStatus();
            };
            ws.onclose = () => {
                isConnected = false;
                updateStatus();
            };
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                latestImages[data.cameraId] = data.image;
                updateImages();
            };
        }

        function sendMessage(message) {
            if (isConnected) {
                ws.send(message);
            } else {
                alert('WebSocket is not connected.');
            }
        }

        function updateImages() {
            const container = document.getElementById('images-container');
            container.innerHTML = '';
            for (const [cameraId, imgSrc] of Object.entries(latestImages)) {
                const div = document.createElement('div');
                const h3 = document.createElement('h3');
                h3.innerText = cameraId;
                const img = document.createElement('img');
                img.className = 'smol-image';
                img.src = imgSrc || '';
                div.appendChild(h3);
                div.appendChild(imgSrc ? img : document.createTextNode('No image available'));
                container.appendChild(div);
            }
        }

        async function callApi(endpoint, method = 'GET') {
            try {
                const response = await fetch(endpoint, { method });
                const data = await response.json();
                document.getElementById('result').innerText = JSON.stringify(data, null, 2);
            } catch (error) {
                document.getElementById('result').innerText = `Error: ${error.message}`;
            }
        }
    </script>
</head>
<body>
    <h1>SkellyCam API Tester with WebSocket</h1>
    <p> WebSocket status: <span id="ws-status">Disconnected</span></p>
    <button onclick="connectWebSocket()">Connect WebSocket</button>
    <button onclick="sendMessage('Hello from the client')">Send WS Message</button>
    <button onclick="callApi('http://localhost:8005/')">Read Root</button>
    <button onclick="callApi('http://localhost:8005/app_state/healthcheck')">Hello👋</button>
    <button onclick="callApi('http://localhost:8005/app_state/shutdown')">goodbye👋</button>
    <button onclick="callApi('http://localhost:8005/cameras/connect/apply', 'POST')">Connect/Update Cameras</button>
    <button onclick="callApi('http://localhost:8005/cameras/connect')">Connect to Cameras</button>
    <button onclick="callApi('http://localhost:8005/cameras/connect/test')">Test Camera Connection</button>
    <button onclick="callApi('http://localhost:8005/cameras/detect')">Detect Cameras</button>
    <button onclick="callApi('http://localhost:8005/cameras/record/start')">Start Recording</button>
    <button onclick="callApi('http://localhost:8005/cameras/record/stop')">Stop Recording</button>
    <button onclick="callApi('http://localhost:8005/cameras/close')">Close Camera Connections</button>
    <pre id="result"></pre>
    <div id="images-container"></div>
</body>
</html>
"""

ui_router = APIRouter()


@ui_router.get("/", response_class=HTMLResponse)
async def serve_ui():
    return HTMLResponse(content=UI_HTML_PAGE)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(ui_router, host="localhost", port=8000)
