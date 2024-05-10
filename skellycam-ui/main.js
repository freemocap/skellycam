const msgpack = msgpack5();
const websocket_route = 'ws://localhost:8003/ws/connect'
const detect_route = 'http://localhost:8003/detect';
const connect_route = 'http://localhost:8003/connect';
const close_route = 'http://localhost:8003/close';
const hello_route = 'http://localhost:8003/hello';
const test_cameras_route = 'http://localhost:8003/connect/test';


// Websocket
const statusElement = document.getElementById('websocket-status');

let ws = null;
let connectWebSocket = async () => {
    addLog(`Connecting to the server via WebSocket at: ${websocket_route}`)
    if (ws) {
        addLog('Resetting WebSocket connection...');
        ws.send('resetting websocket connection...');
        ws.close();
        await new Promise(r => setTimeout(r, 1000));
    }
    ws = new WebSocket(websocket_route);

    ws.onopen = function () {
        addLog(`Connected to the server via WebSocket at: ${websocket_route});`);
    };

    ws.onmessage = function (event) {
        statusElement.textContent = 'WebSocket status: Connected';
        if (typeof event.data === 'string') {
            addLog(`Received string message:${JSON.stringify(event.data, null, 2)}`);
        } else if (event.data instanceof Blob) {
            const reader = new FileReader();
            reader.onload = function () {
                const arrayBuffer = this.result;
                const uint8Array = new Uint8Array(arrayBuffer);
                const payload = msgpack.decode(uint8Array);
                const jpegImagesByCamera = payload.jpeg_images_by_camera;

                Object.keys(jpegImagesByCamera).forEach(cameraId => {
                        const jpegImage = jpegImagesByCamera[cameraId];
                        if (jpegImage) {
                            const image = new Image()
                            image.onload = () => {
                                const canvas = document.getElementById(`camera${cameraId}`) || updateCanvasElements(jpegImagesByCamera)
                                canvas.width = image.width
                                canvas.height = image.height
                                const context = canvas.getContext('2d')
                                context.drawImage(image, 0, 0, canvas.width, canvas.height)
                                URL.revokeObjectURL(image.src)
                            }
                            const blob = new Blob([jpegImage], {type: 'image/jpeg'});

                            const url = URL.createObjectURL(blob)
                            image.src = url
                        }
                    }
                )
                ;
            }
            reader.readAsArrayBuffer(event.data);
        } else {
            console.error(`Received message of unknown type: ${event.data}`);
        }
    }
    ;
    ws.onerror = function (error) {
        console.error('WebSocket error:', error);
    };

    ws.onclose = function () {
        statusElement.textContent = 'WebSocket status: Closed';
        addLog('Disconnected from the server.');
    };
}

function updateCanvasElements(jpegImagesByCamera) {
    const cameras = Object.keys(jpegImagesByCamera);
    const videoContainer = document.getElementById('videoContainer');
    cameras.forEach(cameraId => {
        if (!document.getElementById(`camera${cameraId}`)) {
            const canvas = document.createElement('canvas');
            canvas.id = `camera${cameraId}`;
            canvas.style.border = '1px solid green';
            canvas.style.width = '50%';
            canvas.style.height = 'auto';
            canvas.style.margin = '10px';
            videoContainer.appendChild(canvas);
        }
    });
}


let logCount = 0;

function addLog(message) {
    console.log(message);
    const logContainer = document.getElementById('logContainer');
    const logEntry = document.createElement('div');
    logEntry.textContent = `[${logCount++}] ☞ ${message}`;
    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// buttons
document.getElementById('reset-websocket').onclick = async function () {
    await connectWebSocket();
}

document.getElementById('detect-button').onclick = async function () {
    const response = await fetch(detect_route, {
        method: 'GET',
    });
    const data = await response.json();
    addLog(`Detect request sent - response: ${JSON.stringify(data, null, 2)}`);
}

document.getElementById('connect-button').onclick = async function () {
    const response = await fetch(connect_route, {
        method: 'GET',
    });
    const data = await response.json();
    addLog(`Connect request sent - response: ${JSON.stringify(data, null, 2)}`);
}

document.getElementById('close-button').onclick = async function () {
    const response = await fetch(close_route, {
        method: 'GET',
    });
    const data = await response.json();
    addLog(`Close request sent - response: ${JSON.stringify(data, null, 2)}`);
}

document.getElementById('hello-button').onclick = async function () {
    const response = await fetch(hello_route, {
        method: 'GET',
    });
    const data = await response.json();
    addLog(`Hello request sent - response: ${JSON.stringify(data, null, 2)}`);
}

document.getElementById('test-cameras-button').onclick = async function () {
    addLog(`Sending '/connect/test' GET request`);
    const response = await fetch(test_cameras_route, {
        method: 'GET',
    });
    const data = await response.json();
    addLog(`'/connect/test' request sent - response: ${JSON.stringify(data, null, 2)}`);
}