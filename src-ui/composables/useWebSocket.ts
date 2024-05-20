import type {FrontendImagePayload} from "~/types/types";
import {decode} from "@msgpack/msgpack";

export default (url: string) => {
    const ws = ref<WebSocket | null>(null);
    const messages = ref<string[]>([]);
    const isConnected = ref(false);
    const latestImagePayload = ref<FrontendImagePayload | null>(null);

    const connectWebSocket = () => {
        if (ws.value) {
            ws.value.close();
        }

        ws.value = new WebSocket(url);

        ws.value.onopen = () => {
            console.log('WebSocket connection established');
            isConnected.value = true;
        };

        ws.value.onmessage = async (event) => {
            if (typeof event.data === 'string') {
                messages.value.push(event.data);
            } else if (event.data instanceof Blob) {

                try {
                    const arrayBuffer = await event.data.arrayBuffer();
                    if (arrayBuffer.byteLength < 1000) {
                        console.log('Received small Blob:', arrayBuffer.byteLength);
                        messages.value.push(`Received small Blob: ${arrayBuffer.byteLength} bytes - ${new TextDecoder().decode(arrayBuffer)}`);
                    }
                    console.log('Received Blob with size:', arrayBuffer.byteLength);
                    latestImagePayload.value = decode(new Uint8Array(arrayBuffer)) as FrontendImagePayload;
                    const logMessage = `Updated latestImagePayload with ${latestImagePayload.value?.jpeg_images ? Object.keys(latestImagePayload.value?.jpeg_images).length : 0} cameras`;
                    console.log(logMessage);
                    messages.value.push(logMessage);

                } catch (error) {
                    console.error('Error decoding MessagePack:', error);
                }
            }
        }

        ws.value.onclose = () => {
            console.log('WebSocket connection closed');
            isConnected.value = false;
        };

        ws.value.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    };

    onUnmounted(() => {
        if (ws.value) {
            ws.value.close();
        }
    });

    const sendMessage = (message: string = "hi") => {
        if (ws.value && isConnected.value) {
            ws.value.send(message);
        }
    };
    const handleBlob = async (blob: Blob) => {
        const reader = new FileReader();
        reader.onload = () => {
            if (reader.result) {
                try {
                    console.log(`Handling Blob with size ${reader.result.toString().length}`)
                } catch (error) {
                    console.error('Error parsing JSON from Blob:', error);
                }
            }
        };
        reader.readAsText(blob);  // Read the Blob as text
    };


    return {
        connectWebSocket,
        sendMessage,
        messages,
        isConnected,
    };
}
