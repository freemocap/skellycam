const wsUrl = 'ws://localhost:8005/websocket/connect';
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
                const data = JSON.parse(event.data);
                // const message = parseMessage(data);
                if (data.jpeg_images !== undefined) {
                    latestImages.value = data.jpeg_images
                }
                console.log('Received message:', data);
            } catch (error) {
                console.log(`Failed to parse message as json: ${event}`)
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



    const sendMessage = (message: string = "hi") => {
        if (ws.value && isConnected.value) {
            ws.value.send(message);
        }
    };

    const closeWebsocket = (async () => {
        console.log("Closing websocket...")
        ws.close()
    })

    return {
        connectWebSocket,
        closeWebsocket,
        sendMessage,
        isConnected,
        latestImages,
    };
}
