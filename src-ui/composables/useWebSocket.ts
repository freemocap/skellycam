export default (url: string) =>
{
    const ws = ref<WebSocket | null>(null);
    const messages = ref<string[]>([]);
    const isConnected = ref(false);

    const connectWebSocket = () => {
        if (ws.value) {
            ws.value.close();
        }

        ws.value = new WebSocket(url);

        ws.value.onopen = () => {
            console.log('WebSocket connection established');
            isConnected.value = true;
        };

        ws.value.onmessage = (event) => {
            if (typeof event.data === 'string') {
                messages.value.push(event.data);
            } else if (event.data instanceof Blob) {
                const reader = new FileReader();
                reader.onload = () => {
                    if (reader.result) {
                        messages.value.push(reader.result as string);
                    }
                };
                reader.readAsText(event.data);
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

    const sendMessage = (message: string) => {
        if (ws.value && isConnected.value) {
            ws.value.send(message);
        }
    };

    onUnmounted(() => {
        if (ws.value) {
            ws.value.close();
        }
    });

    return {
        connectWebSocket,
        sendMessage,
        messages,
        isConnected,
    };
}
