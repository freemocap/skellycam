import * as msgpack from '@msgpack/msgpack';

const wsUrl = 'ws://localhost:8005/websocket/connect';

class FrontendFramePayload {
    cameraIds: string[];
    jpegImages: Record<string, string>
    lifespanTimestampsNs: Array<{ [key: string]: bigint }>;

    constructor(payload: any) {
        this.cameraIds = payload.camera_ids || [];
        this.jpegImages = payload.jpeg_images || {}
        this.lifespanTimestampsNs = payload.lifespan_timestamps_ns || [];
    }
}

class RecordingInfo {
    recordingUuid: string;
    recordingName: string;
    recordingFolder: string;
    cameraConfigs: Record<string, any>

    constructor(payload: any) {
        this.recordingUuid = payload.recording_uuid
        this.recordingName = payload.recording_name
        this.recordingFolder = payload.recording_folder
        this.cameraConfigs = payload.camera_configs
    }
}

interface AppState {
    latest_frontend_payload?: FrontendFramePayload;
    recording_info?: RecordingInfo;
}

const _appState: AppState = {};

const _handleWebsocketMessage = (message: string | Buffer): void => {
    if (typeof message === 'string') {
        try {
            const jsonData: any = JSON.parse(message);
            _handleJsonMessage(jsonData);
        } catch (error) {
            if (error instanceof SyntaxError) {
                console.info(`Received text message: ${message}`);
                _handleTextMessage(message);
            }
        }
    } else {
        console.info(`Received binary message: size: ${(message.length * 0.001).toFixed(3)}kB`);
        try {
            const decodedData = msgpack.decode(new Uint8Array(message));
            console.log('Decoded binary message:', decodedData);
            _handleBinaryMessage(message);
        } catch (error) {
            console.error(`Failed to decode binary message: ${error}`);

        }
    }
};

const _handleTextMessage = (message: string): void => {
    console.info(`Received text message: ${message}`);
    // Handle text message
};

const _handleBinaryMessage = (message: Buffer): void => {
    const HELLO_CLIENT_BYTES_MESSAGE = Buffer.from('Hello, Client'); // Replace with actual value

    if (message.equals(HELLO_CLIENT_BYTES_MESSAGE)) {
        console.info('Received HELLO_CLIENT_BYTES_MESSAGE');
        return;
    }

    const payload: any = msgpack.decode(message);

    if ('jpeg_images' in payload) {
        const fePayload = new FrontendFramePayload(payload);
        console.info(
            `Received FrontendFramePayload with ${fePayload.cameraIds.length} cameras - size: ${message.length} bytes`
        );
        fePayload.lifespanTimestampsNs.push({unpickled_from_websocket: process.hrtime.bigint()});
        _appState.latest_frontend_payload = fePayload;
    } else if ('recording_name' in payload) {
        console.debug(`Received RecordingInfo object  - ${JSON.stringify(payload)}`);
        _appState.recording_info = new RecordingInfo(payload);
    } else {
        console.info(`Received binary message: ${(JSON.stringify(payload).length * 0.001).toFixed(3)}kB`);
    }
};

const _handleJsonMessage = (jsonData: any): void => {
    // Handle JSON message
};

export default (url: string = wsUrl) => {
    const ws = ref<WebSocket | null>(null);
    const isConnected = ref(false);
    const latestImages = ref<Record<string, string | null>>({}); // To hold image URLs

    const connectWebSocket = async () => {
        if (ws.value) {
            ws.value.close();
        }

        ws.value = new WebSocket(url);

        ws.value.onopen = () => {
            console.log('WebSocket connection established');
            isConnected.value = true;
        };

        ws.value.onmessage = async (event) => {
            try {
                const data = typeof event.data === 'string' ? event.data : await event.data.arrayBuffer();
                _handleWebsocketMessage(data);

                console.log('Received raw data:', data);
                if (typeof data !== 'string') {
                    const decodedData = msgpack.decode(new Uint8Array(data));
                    console.log('Decoded binary message:', decodedData);
                } else {
                    _handleWebsocketMessage(data);
                    const jsonData = JSON.parse(data);
                    if (jsonData.jpeg_images !== undefined) {
                        latestImages.value = jsonData.jpeg_images;
                    }
                }
            } catch (error) {
                console.error(`Failed to parse message: ${JSON.stringify(event, null, 2)}`);
                console.error('Error details:', error);
            }
        };

        ws.value.onclose = () => {
            console.log('WebSocket connection closed');
            isConnected.value = false;
        };

        ws.value.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    };

    const sendMessage = (message: string = "hi") => {
        if (ws.value && isConnected.value) {
            ws.value.send(message);
        }
    };

    const closeWebsocket = async () => {
        console.log("Closing websocket...");
        if (ws.value) {
            ws.value.close();
        }
    };

    return {
        connectWebSocket,
        closeWebsocket,
        sendMessage,
        isConnected,
        latestImages,
    };
};
