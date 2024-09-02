export default (url: string) => {
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
            if (typeof event.data === 'string') {
                console.log('Received message:', event.data);
            } else if (event.data instanceof Blob) {

                try {
                    const arrayBuffer = await event.data.arrayBuffer();
                    console.log('Received websocketBlob:', arrayBuffer.byteLength);
                    if (arrayBuffer.byteLength < 1000) {
                        // console.log('Received Blob with size:', arrayBuffer.byteLength);
                        // const payload = decode(new Uint8Array(arrayBuffer)) as FrontendImagePayload;
                        // await updateLatestImages(payload);
                        // const logMessage = `Updated latestImages with ${Object.keys(payload.jpeg_images).length} cameras`;
                        // console.log(logMessage);
                    }
                } catch (error) {
                    console.error('Error decoding websocket blob:', error);
                }
            } else {
                console.log(`Received ${event.type}`)
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

    return {
        connectWebSocket,
        sendMessage,
        isConnected,
        latestImages,
    };
}


//
// const updateLatestImages = async (payload: FrontendImagePayload) => {
//     const images = payload.jpeg_images || {};
//     const processedImages: Record<string, string | null> = {};
//
//     for (const [cameraId, imageBytes] of Object.entries(images)) {
//         if (imageBytes) {
//             try {
//                 console.log(`Processing image for camera ${cameraId}`);
//                 const uint8Array = new Uint8Array(imageBytes);
//                 console.log(`Image byte length for camera ${cameraId}:`, uint8Array.byteLength);
//                 const blob = new Blob([uint8Array], {type: 'image/jpeg'});
//                 const url = URL.createObjectURL(blob);
//                 processedImages[cameraId] = url;
//
//                 // Load the image and get its dimensions
//                 const img = new Image();
//                 img.onload = () => {
//                     console.log(`Image dimensions for camera ${cameraId}: width=${img.width}, height=${img.height}`);
//                 };
//                 img.src = url;
//             } catch (error) {
//                 console.error(`Error processing image for camera ${cameraId}:`, error);
//                 processedImages[cameraId] = null;
//             }
//         } else {
//             processedImages[cameraId] = null;
//         }
//     }
//     latestImages.value = processedImages;
// };
