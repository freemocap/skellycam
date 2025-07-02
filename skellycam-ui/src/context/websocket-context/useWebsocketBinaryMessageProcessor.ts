// skellycam-ui/src/context/websocket-context/useBinaryFrameProcessor.ts
import {useCallback, useRef, useState} from 'react';

// Define the message types from the Python code - from skellycam.core.types.numpy_record_dtypes import create_frontend_payload_from_mf_recarray
enum MessageType {
    PAYLOAD_HEADER = 0,
    FRAME_HEADER = 1,
    PAYLOAD_FOOTER = 2
}

// Structure sizes based on the Python dtype definitions
// Note: NumPy's align=True adds padding for memory alignment
const PAYLOAD_HEADER_SIZE = 24; // 1 + 8 + 4 bytes  + alignment padding
const FRAME_HEADER_SIZE = 48;   // 1 + 8 + 16 + 4 + 4 + 4 + 4 bytes + alignment padding
const PAYLOAD_FOOTER_SIZE = 24; // 1 + 8 + 4 bytes + alignment padding

interface MessageHeaderFooter {
    messageType: number;
    frameNumber: number;
    numberOfCameras: number;
}

interface FrameHeader {
    messageType: number;
    frameNumber: number;
    cameraId: string;
    imageWidth: number;
    imageHeight: number;
    colorChannels: number;
    jpegStringLength: number;
}

export const useWebsocketBinaryMessageProcessor = () => {
    const [latestImageBitmaps, setLatestImageBitmaps] = useState<Record<string, ImageBitmap>>({});
    const bitmapCleanupRef = useRef<Record<string, ImageBitmap>>({});
    const [lastProcessedFrameNumber, setLastProcessedFrameNumber] = useState<number>(-1);

    const processBinaryMessage = useCallback(async (data: ArrayBuffer): Promise<number | null> => {
        try {
            const dataView = new DataView(data);
            let offset = 0;

            // Read payload header
            const headerMessageType = dataView.getUint8(offset);
            offset += 1;

            if (headerMessageType !== MessageType.PAYLOAD_HEADER) {
                console.error(`Expected payload header (0), got ${headerMessageType}`);
                return null;
            }

            // Skip 7 bytes of padding (alignment)
            offset += 7;

            // Read frame number (8 bytes)
            const frameNumber = Number(dataView.getBigInt64(offset, true));
            offset += 8;

            // Read number of cameras (4 bytes)
            const numberOfCameras = dataView.getInt32(offset, true);
            offset += 4;

            // Skip remaining padding in the header (4 bytes)
            offset += 4;

            console.info(`Processing frame ${frameNumber} with ${numberOfCameras} cameras`);

            // Process each camera frame
            const newBitmaps: Record<string, ImageBitmap> = {};
            const oldBitmaps = {...bitmapCleanupRef.current};

            if (numberOfCameras <= 0) {
                console.warn(`No cameras found in frame ${frameNumber}`);
                return null;
            }

            for (let i = 0; i < numberOfCameras; i++) {
                // Read frame header
                const frameHeaderMessageType = dataView.getUint8(offset);
                offset += 1;

                if (frameHeaderMessageType !== MessageType.FRAME_HEADER) {
                    console.error(`Expected frame header (1), got ${frameHeaderMessageType}`);
                    return null;
                }

                // Skip 7 bytes of padding (alignment)
                offset += 7;

                const frameHeaderFrameNumber = Number(dataView.getBigInt64(offset, true));
                offset += 8;

                if (frameHeaderFrameNumber !== frameNumber) {
                    console.error(`Frame header mismatch: expected frame ${frameNumber}, got ${frameHeaderFrameNumber}`);
                    return null;
                }

                // Read camera ID (fixed 16 bytes)
                const cameraIdBytes = new Uint8Array(data, offset, 16);
                offset += 16;

                // Find the null terminator
                let cameraIdLength = 0;
                while (cameraIdLength < 16 && cameraIdBytes[cameraIdLength] !== 0) {
                    cameraIdLength++;
                }
                const cameraId = new TextDecoder().decode(cameraIdBytes.slice(0, cameraIdLength));

                const imageWidth = dataView.getInt32(offset, true);
                offset += 4;

                const imageHeight = dataView.getInt32(offset, true);
                offset += 4;

                const colorChannels = dataView.getInt32(offset, true);
                offset += 4;

                const jpegStringLength = dataView.getInt32(offset, true);
                offset += 4;

                // Extract JPEG data
                const jpegData = new Uint8Array(data, offset, jpegStringLength);
                offset += jpegStringLength;

                // Create blob and ImageBitmap
                const blob = new Blob([jpegData], {type: 'image/jpeg'});
                try {
                    const bitmap = await createImageBitmap(blob);
                    newBitmaps[cameraId] = bitmap;
                } catch (error) {
                    console.error(`Failed to create ImageBitmap for camera ${cameraId}:`, error);
                }
            }

            // Read payload footer
            const footerMessageType = dataView.getUint8(offset);
            offset += 1;

            if (footerMessageType !== MessageType.PAYLOAD_FOOTER) {
                console.error(`Expected payload footer (2), got ${footerMessageType}`);
                return null;
            }

            // Skip 7 bytes of padding (alignment)
            offset += 7;

            const footerFrameNumber = Number(dataView.getBigInt64(offset, true));
            offset += 8;

            const footerNumberOfCameras = dataView.getInt32(offset, true);
            offset += 4;

            // Verify footer matches header
            if (footerFrameNumber !== frameNumber || footerNumberOfCameras !== numberOfCameras) {
                console.error(`Footer mismatch: expected frame ${frameNumber}/${numberOfCameras}, got ${footerFrameNumber}/${footerNumberOfCameras}`);
                return null;
            }

            // Update state with new bitmaps
            bitmapCleanupRef.current = {...newBitmaps};
            setLatestImageBitmaps(newBitmaps);
            setLastProcessedFrameNumber(frameNumber);

            // Clean up old bitmaps
            queueMicrotask(() => {
                Object.values(oldBitmaps).forEach(bitmap => {
                    bitmap.close();
                });
            });

            return frameNumber;
        } catch (error) {
            console.error('Error processing binary frame:', error);
            return null;
        }
    }, []);

    return {
        latestImageBitmaps,
        lastProcessedFrameNumber,
        processBinaryMessage
    };
};
